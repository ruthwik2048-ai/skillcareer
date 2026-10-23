import calendar
from datetime import date
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.utils import timezone
from django.dispatch import receiver


def add_one_calendar_month(day):
    month_index = day.month
    year = day.year + (month_index // 12)
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def default_job_deadline():
    return add_one_calendar_month(timezone.localdate())


def application_resume_path(instance, filename):
    return f"job_applications/{instance.student_id}/{uuid4().hex}.pdf"


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="student_profile",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    roll_number = models.CharField(max_length=30, unique=True)
    login_code = models.CharField(max_length=6, blank=True, default="", editable=False)
    teach_skills = models.JSONField(default=list, blank=True)
    learn_skills = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class StudentLoginCode(Student):
    class Meta:
        proxy = True
        verbose_name = "student login code"
        verbose_name_plural = "student login codes"


class StudentRegistrationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=100)
    email = models.EmailField()
    teach_skills = models.JSONField(default=list, blank=True)
    learn_skills = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at", "name"]

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.get_status_display()}"


class LearningBatch(models.Model):
    name = models.CharField(max_length=100)
    created_by_student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        related_name="created_batches",
        null=True,
        blank=True,
    )
    created_by_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_learning_batches",
        null=True,
        blank=True,
        verbose_name="Created by admin",
    )
    members = models.ManyToManyField(Student, related_name="learning_batches")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self):
        return self.name


class Job(models.Model):
    title = models.CharField(max_length=150)
    company = models.CharField(max_length=150)
    location = models.CharField(max_length=150, blank=True)
    description = models.TextField()
    required_skills = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated skills used to recommend this job.",
    )
    application_deadline = models.DateField(default=default_job_deadline)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    renewed_from = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        related_name="renewed_job",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at", "title"]

    def __str__(self):
        return f"{self.title} at {self.company}"

    @property
    def is_open(self):
        return self.is_active and self.application_deadline >= timezone.localdate()


class JobApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "Under review"
        INTERVIEW = "interview", "Interview"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    resume = models.FileField(upload_to=application_resume_path)
    cover_note = models.TextField(blank=True, max_length=3000)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "job"],
                name="unique_job_application_per_student",
            )
        ]

    def __str__(self):
        return f"{self.student.name} - {self.job.title}"


@receiver(post_delete, sender=JobApplication)
def delete_application_resume(sender, instance, **kwargs):
    if instance.resume:
        instance.resume.delete(save=False)
