import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    JobApplicationForm,
    LearningBatchUpdateForm,
    StudentAuthenticationForm,
    StudentForm,
    StudentRegistrationRequestForm,
)
from .models import (
    Job,
    JobApplication,
    LearningBatch,
    Student,
    StudentRegistrationRequest,
)
from .services import calculate_match, recommend_career_roles


logger = logging.getLogger(__name__)


def _get_student(student_id):
    return get_object_or_404(Student, pk=student_id)


def _matching_students(student):
    matches = []
    for other_student in Student.objects.exclude(
        pk=student.pk,
    ).exclude(email__iexact=student.email):
        can_teach, can_learn, percentage = calculate_match(student, other_student)
        if percentage > 0:
            matches.append(
                {
                    "student": other_student,
                    "can_teach": sorted(can_teach),
                    "can_learn": sorted(can_learn),
                    "percentage": percentage,
                }
            )
    return matches


def student_list(request):
    students = Student.objects.all()
    for student in students:
        student.recommended_jobs = recommend_career_roles(student.teach_skills)
    return render(request, "matching/students.html", {"students": students})


def delete_student(request, student_id):
    student = _get_student(student_id)
    if request.method == "POST":
        student.delete()
        return redirect("student-list")

    return render(
        request,
        "matching/student_delete.html",
        {"student": student},
    )


def request_student_registration(request):
    submitted = request.method == "POST"
    form = StudentRegistrationRequestForm(
        request.POST if submitted else None,
    )
    if submitted and form.is_valid():
        form.save()
        return render(
            request,
            "matching/join_request.html",
            {"submitted": True},
        )

    return render(
        request,
        "matching/join_request.html",
        {"form": form, "submitted": False},
    )


def update_student(request, student_id):
    student = _get_student(student_id)
    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect("student-list")
    else:
        form = StudentForm(
            instance=student,
            initial={
                "teach_skills": ", ".join(student.teach_skills),
                "learn_skills": ", ".join(student.learn_skills),
            },
        )

    return render(
        request,
        "matching/profile_form.html",
        {"form": form, "student": student},
    )


def student_matches(request, student_id):
    student = _get_student(student_id)
    matches = _matching_students(student)

    return render(
        request,
        "matching/matches.html",
        {
            "student": student,
            "matches": matches,
        },
    )


def learning_batches(request):
    batches = (
        LearningBatch.objects.prefetch_related("members")
        .select_related("created_by_admin", "created_by_student")
    )
    return render(
        request,
        "matching/batches.html",
        {"batches": batches},
    )


def update_learning_batch(request, batch_id):
    batch = get_object_or_404(LearningBatch, pk=batch_id)
    if request.method == "POST":
        form = LearningBatchUpdateForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            return redirect("learning-batches")
    else:
        form = LearningBatchUpdateForm(instance=batch)

    return render(
        request,
        "matching/batch_form.html",
        {"form": form, "batch": batch},
    )


def student_login(request):
    form = StudentAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not Student.objects.filter(user=user).exists():
            form.add_error(None, "This account is not linked to a student profile.")
        else:
            auth_login(request, user)
            return redirect("student-dashboard")

    return render(request, "matching/login.html", {"form": form})


@login_required(login_url="student-login")
def student_logout(request):
    if request.method != "POST":
        return redirect("student-dashboard")
    auth_logout(request)
    return redirect("job-list")


@login_required(login_url="student-login")
def student_dashboard(request):
    student = get_object_or_404(
        Student.objects.select_related("user"),
        user=request.user,
    )
    applications = student.job_applications.select_related("job")
    return render(
        request,
        "matching/dashboard.html",
        {"student": student, "applications": applications},
    )


def job_list(request, student_id=None):
    jobs = [job for job in Job.objects.filter(is_active=True) if job.is_open]
    student = None
    if request.user.is_authenticated:
        student = Student.objects.filter(user=request.user).first()
    skill_profile = (
        _get_student(student_id)
        if student_id is not None
        else student
    )

    for job in jobs:
        job.required_skill_list = [
            skill.strip().casefold()
            for skill in job.required_skills.split(",")
            if skill.strip()
        ]
        student_skills = (
            {
                skill.strip().casefold()
                for skill in skill_profile.teach_skills
                if skill.strip()
            }
            if skill_profile
            else set()
        )
        job.matched_skills = (
            sorted(student_skills & set(job.required_skill_list))
        )
        job.already_applied = (
            student is not None
            and JobApplication.objects.filter(student=student, job=job).exists()
        )
    if student_id is not None:
        jobs = [job for job in jobs if job.matched_skills]
    jobs.sort(key=lambda job: (-len(job.matched_skills), -job.pk))
    return render(
        request,
        "matching/jobs.html",
        {
            "jobs": jobs,
            "student": student,
            "skill_profile": skill_profile,
            "show_matching_jobs": student_id is not None,
        },
    )


@login_required(login_url="student-login")
def apply_for_job(request, job_id):
    student = get_object_or_404(Student, user=request.user)
    job = get_object_or_404(Job, pk=job_id, is_active=True)
    if not job.is_open:
        raise Http404("This job is no longer accepting applications.")
    if JobApplication.objects.filter(student=student, job=job).exists():
        return redirect("student-dashboard")

    form = JobApplicationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.student = student
        application.job = job
        application.save()
        try:
            email_sent = send_mail(
                subject=f"Application submitted: {job.title}",
                message=(
                    f"Congratulations, {student.name}!\n\n"
                    f"Your application for {job.title} at {job.company} "
                    "has been submitted successfully.\n\n"
                    "You can track your application status from your "
                    "SkillCareer student dashboard.\n\n"
                    "Best wishes,\n"
                    "SkillCareer"
                ),
                from_email=None,
                recipient_list=[student.email],
                fail_silently=False,
            )
        except (OSError, SMTPException):
            logger.exception(
                "Could not send job application confirmation to %s",
                student.email,
            )
            messages.warning(
                request,
                "Your application was submitted, but we could not send the "
                "confirmation email. Please check the email service configuration.",
            )
        else:
            if email_sent:
                if settings.EMAIL_BACKEND.endswith(".console.EmailBackend"):
                    messages.info(
                        request,
                        "Application submitted. The confirmation email was "
                        "printed to the development server console; configure "
                        "SMTP to deliver it to the student's inbox.",
                    )
                else:
                    messages.success(
                        request,
                        f"Application submitted. A confirmation email was sent "
                        f"to {student.email}.",
                    )
            else:
                logger.error(
                    "Email backend did not send job application confirmation to %s",
                    student.email,
                )
                messages.warning(
                    request,
                    "Your application was submitted, but we could not send the "
                    "confirmation email. Please check the email service configuration.",
                )
        return redirect("student-dashboard")

    return render(
        request,
        "matching/apply_form.html",
        {"form": form, "job": job},
    )


@login_required(login_url="student-login")
def download_application_resume(request, application_id):
    application = get_object_or_404(
        JobApplication.objects.select_related("student", "job"),
        pk=application_id,
    )
    if not request.user.is_staff and application.student.user_id != request.user.pk:
        raise Http404
    if not application.resume or not application.resume.storage.exists(
        application.resume.name
    ):
        raise Http404("Resume file not found.")
    return FileResponse(
        application.resume.open("rb"),
        as_attachment=True,
        filename=f"{application.student.roll_number}-resume.pdf",
        content_type="application/pdf",
    )
