import re
import tempfile
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Job,
    JobApplication,
    LearningBatch,
    Student,
    StudentLoginCode,
    StudentRegistrationRequest,
)
from .services import calculate_match, recommend_career_roles


class SkillMatchingTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        self.alex = Student.objects.create(
            name="Alex",
            email="alex@example.com",
            roll_number="SW1001",
            teach_skills=["python"],
            learn_skills=["design"],
        )
        self.sam = Student.objects.create(
            name="Sam",
            email="sam@example.com",
            roll_number="SW1002",
            teach_skills=["design"],
            learn_skills=["python"],
        )

    def test_calculate_match_finds_both_directions(self):
        can_teach, can_learn, percentage = calculate_match(self.alex, self.sam)

        self.assertEqual(can_teach, {"python"})
        self.assertEqual(can_learn, {"design"})
        self.assertEqual(percentage, 100)

    def test_student_list_displays_registered_students(self):
        response = self.client.get(reverse("student-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex")
        self.assertContains(response, "Sam")
        self.assertContains(response, "Roll number: SW1001")
        self.assertContains(response, "Update student")
        self.assertContains(response, "Delete student")
        self.assertContains(
            response,
            f'href="{reverse("student-list")}#exchange">Explore',
        )
        self.assertContains(response, 'id="exchange"')
        self.assertContains(response, "Apply for jobs")
        self.assertContains(
            response,
            reverse("student-jobs", args=[self.alex.pk]),
        )

    def test_registration_request_waits_for_admin_approval(self):
        response = self.client.post(
            reverse("register-student"),
            {
                "name": "Taylor",
                "email": "taylor@example.com",
                "teach_skills": "Python, Django",
                "learn_skills": "Design",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "awaiting admin approval")
        self.assertFalse(Student.objects.filter(email="taylor@example.com").exists())
        registration_request = StudentRegistrationRequest.objects.get(
            email="taylor@example.com"
        )
        self.assertEqual(registration_request.status, "pending")
        self.assertEqual(registration_request.teach_skills, ["python", "django"])
        self.assertEqual(registration_request.learn_skills, ["design"])

        staff = get_user_model().objects.create_superuser(
            username="student-admin",
            email="student-admin@example.com",
            password="test-password",
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("admin:matching_studentregistrationrequest_changelist"),
            {
                "action": "approve_requests",
                "_selected_action": [registration_request.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        registration_request.refresh_from_db()
        student = Student.objects.get(email="taylor@example.com")
        self.assertEqual(registration_request.status, "approved")
        self.assertIsNotNone(registration_request.reviewed_at)
        self.assertEqual(student.teach_skills, ["python", "django"])
        self.assertEqual(student.learn_skills, ["design"])
        self.assertIsNotNone(student.user)
        self.assertEqual(student.user.get_username(), student.roll_number)
        approval_messages = [
            str(message) for message in get_messages(response.wsgi_request)
        ]
        credential = re.search(
            rf"{re.escape(student.roll_number)} / (\d{{6}})",
            " ".join(approval_messages),
        )
        self.assertIsNotNone(credential)
        password = credential.group(1)
        self.assertEqual(student.login_code, password)
        self.assertTrue(student.user.check_password(password))

        request_list_url = reverse(
            "admin:matching_studentregistrationrequest_changelist"
        )
        pending_response = self.client.get(request_list_url)
        self.assertNotContains(pending_response, "taylor@example.com")
        history_response = self.client.get(
            request_list_url,
            {"status__exact": "approved"},
        )
        self.assertContains(history_response, "taylor@example.com")
        login_response = self.client.post(
            reverse("student-login"),
            {"username": student.roll_number, "password": password},
        )
        self.assertRedirects(login_response, reverse("student-dashboard"))

    def test_admin_add_creates_linked_login_and_shows_six_digit_password(self):
        staff = get_user_model().objects.create_superuser(
            username="new-student-admin",
            email="new-student-admin@example.com",
            password="admin-password",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin:matching_student_add"),
            {
                "name": "Morgan",
                "email": "morgan@example.com",
                "roll_number": "SW9001",
                "teach_skills": '["python"]',
                "learn_skills": '["design"]',
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        student = Student.objects.get(email="morgan@example.com")
        self.assertIsNotNone(student.user)
        self.assertEqual(student.user.get_username(), "SW9001")
        self.assertRegex(student.login_code, r"^\d{6}$")
        messages = " ".join(
            str(message) for message in get_messages(response.wsgi_request)
        )
        credential = re.search(r"initial six-digit password: (\d{6})", messages)
        self.assertIsNotNone(credential)
        password = credential.group(1)
        self.assertTrue(student.user.check_password(password))

        login_response = self.client.post(
            reverse("student-login"),
            {"username": "sw9001", "password": password},
        )
        self.assertRedirects(login_response, reverse("student-dashboard"))

    def test_student_login_code_admin_lists_all_students_and_can_generate_legacy_code(self):
        staff = get_user_model().objects.create_superuser(
            username="code-admin",
            email="code-admin@example.com",
            password="admin-password",
        )
        self.client.force_login(staff)
        code_list_url = reverse("admin:matching_studentlogincode_changelist")

        response = self.client.get(code_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex")
        self.assertContains(response, "Sam")
        self.assertContains(response, "Not generated")
        self.assertEqual(StudentLoginCode.objects.count(), 2)

        response = self.client.post(
            code_list_url,
            {
                "action": "generate_login_codes",
                "_selected_action": [self.alex.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.alex.refresh_from_db()
        self.assertRegex(self.alex.login_code, r"^\d{6}$")
        self.assertTrue(self.alex.user.check_password(self.alex.login_code))

    def test_rejected_registration_request_leaves_pending_queue(self):
        registration_request = StudentRegistrationRequest.objects.create(
            name="Jordan",
            email="jordan@example.com",
            teach_skills=["python"],
            learn_skills=["design"],
        )
        staff = get_user_model().objects.create_superuser(
            username="request-admin",
            email="request-admin@example.com",
            password="request-test-password",
        )
        self.client.force_login(staff)
        request_list_url = reverse(
            "admin:matching_studentregistrationrequest_changelist"
        )

        response = self.client.post(
            request_list_url,
            {
                "action": "reject_requests",
                "_selected_action": [registration_request.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        registration_request.refresh_from_db()
        self.assertEqual(registration_request.status, "rejected")
        self.assertIsNotNone(registration_request.reviewed_at)
        self.assertNotContains(self.client.get(request_list_url), "jordan@example.com")
        self.assertContains(
            self.client.get(request_list_url, {"status__exact": "rejected"}),
            "jordan@example.com",
        )

    def test_registration_request_admin_relabels_run_action_button(self):
        staff = get_user_model().objects.create_superuser(
            username="student-admin",
            email="student-admin@example.com",
            password="test-password",
        )
        self.client.force_login(staff)

        response = self.client.get(
            reverse("admin:matching_studentregistrationrequest_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "matching/request_actions.js",
        )
        self.assertTemplateUsed(
            response,
            "admin/matching/studentregistrationrequest/change_list.html",
        )

    def test_student_can_update_profile_and_roll_number(self):
        url = reverse("update-student", args=[self.alex.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Update Alex's profile")

        response = self.client.post(
            url,
            {
                "name": "Alex Updated",
                "email": self.alex.email,
                "roll_number": " sw2001 ",
                "teach_skills": "python, django",
                "learn_skills": "design",
            },
        )

        self.assertRedirects(response, reverse("student-list"))
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.name, "Alex Updated")
        self.assertEqual(self.alex.roll_number, "SW2001")
        self.assertEqual(self.alex.teach_skills, ["python", "django"])

    def test_student_list_shows_career_ideas_from_teachable_skills(self):
        self.alex.teach_skills = ["python", "django"]
        self.alex.save(update_fields=["teach_skills"])

        response = self.client.get(reverse("student-list"))

        self.assertContains(response, "Career ideas based on skills you can teach")
        self.assertContains(response, "Backend Developer")
        self.assertContains(response, "Matching skills: django, python")

    def test_career_recommendations_are_ranked_capped_and_skip_unknown_skills(self):
        recommendations = recommend_career_roles(
            ["python", "django", "sql", "java", "design", "unmapped skill"],
            limit=3,
        )

        self.assertEqual(len(recommendations), 3)
        self.assertEqual(recommendations[0]["title"], "Backend Developer")
        self.assertEqual(
            recommendations[0]["matched_skills"],
            ["django", "java", "python", "sql"],
        )
        self.assertEqual(recommend_career_roles(["unmapped skill"]), [])

    def test_student_delete_confirmation_is_available_without_sign_in(self):
        response = self.client.get(
            reverse("delete-student", args=[self.alex.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "permanently deletes")
        self.assertTrue(Student.objects.filter(pk=self.alex.pk).exists())

    def test_student_delete_removes_student_after_confirmation(self):
        batch = LearningBatch.objects.create(
            name="Alex's batch",
            created_by_student=self.alex,
        )
        batch.members.add(self.alex, self.sam)
        url = reverse("delete-student", args=[self.alex.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "permanently deletes")
        self.assertTrue(Student.objects.filter(pk=self.alex.pk).exists())

        response = self.client.post(url)

        self.assertRedirects(response, reverse("student-list"))
        self.assertFalse(Student.objects.filter(pk=self.alex.pk).exists())
        batch.refresh_from_db()
        self.assertIsNone(batch.created_by_student)
        self.assertSetEqual(set(batch.members.all()), {self.sam})

    def test_sign_in_is_removed(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(self.client.get(reverse("student-list")), "Sign in")

    def test_password_visibility_toggle_is_loaded_for_admin_login(self):
        response = self.client.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "matching/admin.js")
        self.assertContains(response, 'type="password"')
        self.assertContains(response, '<body class=" login"')

    def test_admin_login_opens_admin_page(self):
        get_user_model().objects.create_superuser(
            username="admin-login",
            email="admin-login@example.com",
            password="admin-password",
        )

        response = self.client.post(
            reverse("admin:login"),
            {
                "username": "admin-login",
                "password": "admin-password",
                "next": reverse("admin:index"),
            },
        )

        self.assertRedirects(response, reverse("admin:index"))
        admin_response = self.client.get(reverse("admin:index"))
        self.assertEqual(admin_response.status_code, 200)

    def test_admin_login_has_forgot_password_button(self):
        response = self.client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forgot password?")
        self.assertContains(response, reverse("admin_password_reset"))

    def test_admin_password_reset_sends_email_only_to_staff_user(self):
        staff_user = get_user_model().objects.create_user(
            username="staff-reset",
            email="staff-reset@example.com",
            password="old-admin-password",
            is_staff=True,
            is_active=True,
        )
        student_user = get_user_model().objects.create_user(
            username="student-reset",
            email="student-reset@example.com",
            password="old-student-password",
            is_staff=False,
            is_active=True,
        )
        reset_url = reverse("admin_password_reset")

        response = self.client.post(
            reset_url,
            {"email": student_user.email},
        )
        self.assertRedirects(response, reverse("admin_password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        student_user.refresh_from_db()
        self.assertTrue(student_user.check_password("old-student-password"))

        response = self.client.post(
            reset_url,
            {"email": staff_user.email},
        )
        self.assertRedirects(response, reverse("admin_password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [staff_user.email])
        self.assertIn("/admin/reset/", mail.outbox[0].body)

    def test_match_page_displays_reciprocal_skills(self):
        response = self.client.get(
            reverse("student-matches", args=[self.alex.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sam")
        self.assertContains(response, "python")
        self.assertContains(response, "design")
        self.assertContains(response, "100.00%")

    def test_students_cannot_create_batches_from_the_public_site(self):
        match_response = self.client.get(
            reverse("student-matches", args=[self.alex.pk])
        )
        self.assertNotContains(match_response, "Create a batch from your matches")
        self.assertNotContains(match_response, "Create learning batch")

        response = self.client.post(
            f"/students/{self.alex.pk}/batches/create/",
            {"name": "No matches"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(LearningBatch.objects.exists())

    def test_staff_can_create_batches_in_django_admin(self):
        staff = get_user_model().objects.create_superuser(
            username="batch-admin",
            email="batch-admin@example.com",
            password="test-password",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:matching_learningbatch_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add learning batch")
        self.assertContains(response, "Created by admin")
        self.assertContains(response, "batch-admin")
        self.assertContains(response, "Members:")

        response = self.client.post(
            reverse("admin:matching_learningbatch_add"),
            {
                "name": "Python exchange",
                "created_by_admin": staff.pk,
                "members": [self.alex.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        batch = LearningBatch.objects.get(name="Python exchange")
        self.assertEqual(batch.created_by_admin, staff)
        self.assertSetEqual(set(batch.members.all()), {self.alex})

    def test_batch_edit_is_available_without_sign_in(self):
        batch = LearningBatch.objects.create(
            name="Python exchange",
            created_by_student=self.alex,
        )

        response = self.client.get(
            reverse("update-learning-batch", args=[batch.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Python exchange")
        batch.refresh_from_db()
        self.assertEqual(batch.name, "Python exchange")

    def test_student_can_edit_batch_name_and_members_without_sign_in(self):
        batch = LearningBatch.objects.create(
            name="Python exchange",
            created_by_student=self.alex,
        )
        batch.members.add(self.alex)
        list_response = self.client.get(reverse("learning-batches"))
        self.assertContains(list_response, "Edit batch")

        response = self.client.post(
            reverse("update-learning-batch", args=[batch.pk]),
            {"name": "Updated Python group", "members": [self.sam.pk]},
        )

        self.assertRedirects(response, reverse("learning-batches"))
        batch.refresh_from_db()
        self.assertEqual(batch.name, "Updated Python group")
        self.assertSetEqual(set(batch.members.all()), {self.sam})

    def test_job_board_shows_open_jobs_and_matches_student_skills(self):
        job = Job.objects.create(
            title="Junior Python Developer",
            company="Example Tech",
            description="Build Python services.",
            required_skills="PYTHON, django",
        )
        Job.objects.create(
            title="Closed role",
            company="Old Company",
            description="This role is closed.",
            is_active=False,
        )

        response = self.client.get(reverse("job-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, job.title)
        self.assertNotContains(response, "Closed role")
        self.assertNotContains(response, "Matching skills: python")

        student_user = get_user_model().objects.create_user(
            username="alex",
            email=self.alex.email,
            password="student-password",
        )
        self.alex.user = student_user
        self.alex.save(update_fields=["user"])
        self.client.force_login(student_user)

        job_id = job.pk
        response = self.client.get(reverse("job-list"))
        self.assertContains(response, "python")
        matched_job = next(
            listed_job
            for listed_job in response.context["jobs"]
            if listed_job.pk == job_id
        )
        self.assertEqual(matched_job.matched_skills, ["python"])

    def test_student_jobs_page_only_shows_open_jobs_matching_profile_skills(self):
        matching_job = Job.objects.create(
            title="Python developer",
            company="Example Tech",
            description="Build Python services.",
            required_skills="PYTHON, django",
        )
        Job.objects.create(
            title="Designer",
            company="Example Design",
            description="Create visual designs.",
            required_skills="design",
        )
        Job.objects.create(
            title="Closed Python role",
            company="Old Company",
            description="This role is closed.",
            required_skills="python",
            is_active=False,
        )

        response = self.client.get(
            reverse("student-jobs", args=[self.alex.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching_job.title)
        self.assertNotContains(response, "Designer")
        self.assertNotContains(response, "Closed Python role")
        self.assertEqual(response.context["jobs"][0].matched_skills, ["python"])

    def test_expired_active_job_is_renewed_once_with_one_calendar_month(self):
        expired_job = Job.objects.create(
            title="Python developer",
            company="Example Tech",
            description="Build Python services.",
            required_skills="python",
            application_deadline=date(2026, 1, 30),
        )
        inactive_job = Job.objects.create(
            title="Inactive job",
            company="Example Tech",
            description="This job was manually deactivated.",
            application_deadline=date(2026, 1, 30),
            is_active=False,
        )

        with patch(
            "matching.management.commands.renew_expired_jobs.timezone.localdate",
            return_value=date(2026, 1, 31),
        ):
            call_command("renew_expired_jobs", verbosity=0)
            call_command("renew_expired_jobs", verbosity=0)

        renewed_job = Job.objects.get(renewed_from=expired_job)
        self.assertEqual(renewed_job.title, expired_job.title)
        self.assertEqual(renewed_job.company, expired_job.company)
        self.assertEqual(renewed_job.required_skills, expired_job.required_skills)
        self.assertEqual(renewed_job.application_deadline, date(2026, 2, 28))
        self.assertTrue(renewed_job.is_active)
        self.assertFalse(Job.objects.filter(renewed_from=inactive_job).exists())
        self.assertEqual(Job.objects.filter(renewed_from=expired_job).count(), 1)

    def test_job_deadline_defaults_to_one_calendar_month(self):
        with patch(
            "matching.models.timezone.localdate",
            return_value=date(2026, 1, 31),
        ):
            job = Job.objects.create(
                title="Developer",
                company="Example Tech",
                description="Build software.",
            )

        self.assertEqual(job.application_deadline, date(2026, 2, 28))

    def test_student_login_accepts_only_linked_accounts(self):
        user = get_user_model().objects.create_user(
            username="alex",
            email=self.alex.email,
            password="student-password",
        )
        response = self.client.post(
            reverse("student-login"),
            {"username": "alex", "password": "student-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not linked to a student profile")

        self.alex.user = user
        self.alex.save(update_fields=["user"])
        response = self.client.post(
            reverse("student-login"),
            {"username": "aLeX", "password": "student-password"},
        )
        self.assertRedirects(response, reverse("student-dashboard"))
        self.assertEqual(
            self.client.get(reverse("student-dashboard")).status_code,
            200,
        )

    def test_student_login_explains_case_sensitive_password(self):
        user = get_user_model().objects.create_user(
            username="alex",
            email=self.alex.email,
            password="student-password",
        )
        self.alex.user = user
        self.alex.save(update_fields=["user"])

        response = self.client.post(
            reverse("student-login"),
            {"username": "ALEX", "password": "STUDENT-PASSWORD"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "passwords are case-sensitive")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_student_login_labels_username_as_roll_number(self):
        response = self.client.get(reverse("student-login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roll number (username)")
        self.assertContains(response, "SW000001")
        self.assertContains(response, "matching/password_toggle.js")
        self.assertContains(response, 'data-password-visibility="true"')
        self.assertContains(response, '<button class="login-clear" type="reset">Clear</button>')

    def test_admin_can_manage_job_listings_and_applications(self):
        staff = get_user_model().objects.create_user(
            username="jobs-admin",
            email="jobs-admin@example.com",
            password="admin-password",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff)

        jobs_response = self.client.get(reverse("admin:matching_job_changelist"))
        applications_response = self.client.get(
            reverse("admin:matching_jobapplication_changelist")
        )

        self.assertEqual(jobs_response.status_code, 200)
        self.assertEqual(applications_response.status_code, 200)

    def test_student_dashboard_requires_login_and_shows_only_own_applications(self):
        response = self.client.get(reverse("student-dashboard"))
        self.assertRedirects(
            response,
            f"{reverse('student-login')}?next={reverse('student-dashboard')}",
        )

        job = Job.objects.create(
            title="Junior Python Developer",
            company="Example Tech",
            description="Build Python services.",
        )
        user = get_user_model().objects.create_user(
            username="alex",
            email=self.alex.email,
            password="student-password",
        )
        self.alex.user = user
        self.alex.save(update_fields=["user"])
        application = JobApplication.objects.create(
            student=self.alex,
            job=job,
            resume=SimpleUploadedFile(
                "resume.pdf",
                b"%PDF-1.4\nstudent resume",
                content_type="application/pdf",
            ),
            cover_note="I enjoy building with Python.",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("student-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, job.title)
        self.assertContains(response, "Submitted")
        self.assertContains(
            response,
            reverse("download-application-resume", args=[application.pk]),
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="SkillCareer <theskillcareer.hub@gmail.com>",
    )
    def test_student_can_apply_once_with_pdf_resume(self):
        job = Job.objects.create(
            title="Junior Python Developer",
            company="Example Tech",
            description="Build Python services.",
            required_skills="python",
        )
        user = get_user_model().objects.create_user(
            username="alex",
            email=self.alex.email,
            password="student-password",
        )
        self.alex.user = user
        self.alex.save(update_fields=["user"])
        apply_url = reverse("apply-for-job", args=[job.pk])

        response = self.client.get(apply_url)
        self.assertRedirects(
            response,
            f"{reverse('student-login')}?next={apply_url}",
        )

        self.client.force_login(user)
        response = self.client.post(
            apply_url,
            {
                "cover_note": "I have Python experience.",
                "resume": SimpleUploadedFile(
                    "resume.pdf",
                    b"%PDF-1.4\nstudent resume",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertRedirects(response, reverse("student-dashboard"))
        application = JobApplication.objects.get(student=self.alex, job=job)
        self.assertEqual(application.status, JobApplication.Status.SUBMITTED)
        self.assertEqual(application.cover_note, "I have Python experience.")
        self.assertFalse(application.resume.url in response.content.decode())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.alex.email])
        self.assertIn(job.title, mail.outbox[0].subject)
        self.assertIn("Congratulations, Alex", mail.outbox[0].body)
        self.assertIn(job.company, mail.outbox[0].body)

        response = self.client.get(apply_url)
        self.assertRedirects(response, reverse("student-dashboard"))
        self.assertEqual(
            JobApplication.objects.filter(student=self.alex, job=job).count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_resume_is_rejected_and_private_file_is_owner_only(self):
        job = Job.objects.create(
            title="Developer",
            company="Example Tech",
            description="Build software.",
        )
        alex_user = get_user_model().objects.create_user(
            username="alex",
            email=self.alex.email,
            password="student-password",
        )
        self.alex.user = alex_user
        self.alex.save(update_fields=["user"])
        self.client.force_login(alex_user)

        response = self.client.post(
            reverse("apply-for-job", args=[job.pk]),
            {
                "resume": SimpleUploadedFile(
                    "not-a-pdf.txt",
                    b"not a pdf",
                    content_type="text/plain",
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload your resume as a PDF")
        self.assertFalse(JobApplication.objects.exists())

        application = JobApplication.objects.create(
            student=self.alex,
            job=job,
            resume=SimpleUploadedFile(
                "resume.pdf",
                b"%PDF-1.4\nstudent resume",
                content_type="application/pdf",
            ),
        )
        response = self.client.get(
            reverse("download-application-resume", args=[application.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        response.close()

        sam_user = get_user_model().objects.create_user(
            username="sam",
            email=self.sam.email,
            password="student-password",
        )
        self.sam.user = sam_user
        self.sam.save(update_fields=["user"])
        self.client.force_login(sam_user)
        response = self.client.get(
            reverse("download-application-resume", args=[application.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_rejects_duplicate_student_email_case_insensitively(self):
        staff = get_user_model().objects.create_superuser(
            username="duplicate-admin",
            email="duplicate-admin@example.com",
            password="test-password",
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("admin:matching_student_add"),
            {
                "name": "Alex duplicate",
                "email": self.alex.email.upper(),
                "roll_number": "SW1003",
                "teach_skills": '["python"]',
                "learn_skills": '["design"]',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Student.objects.filter(email__iexact=self.alex.email).count(),
            1,
        )
        self.assertContains(response, "A profile already uses this email.")

    def test_navigation_offers_registration_without_sign_in(self):
        response = self.client.get(reverse("student-list"))
        self.assertContains(response, "Join the community")
        self.assertContains(response, reverse("register-student"))
        self.assertNotContains(response, "Sign in")
        self.assertContains(response, "Find skill matches")
        self.assertContains(response, "Batches")

    def test_manage_students_link_is_only_shown_to_staff(self):
        self.assertNotContains(
            self.client.get(reverse("student-list")),
            "Manage students",
        )

        staff = get_user_model().objects.create_user(
            username="staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("student-list"))

        self.assertContains(response, "Manage students")
        self.assertContains(
            response,
            reverse("admin:matching_student_changelist"),
        )
