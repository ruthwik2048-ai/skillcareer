from django.contrib import messages
from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone

from .forms import StudentForm
from .models import (
    Job,
    JobApplication,
    LearningBatch,
    Student,
    StudentLoginCode,
    StudentRegistrationRequest,
)
from .services import (
    create_student_login,
    reset_student_login_code,
    sync_student_login_username,
    validate_student_login_username,
)


class StudentAdminForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = "__all__"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing_profiles = Student.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing_profiles = existing_profiles.exclude(pk=self.instance.pk)
        if existing_profiles.exists():
            raise forms.ValidationError("A profile already uses this email.")
        return email

    def clean_roll_number(self):
        roll_number = self.cleaned_data["roll_number"].strip().upper()
        existing_profiles = Student.objects.filter(roll_number__iexact=roll_number)
        if self.instance.pk:
            existing_profiles = existing_profiles.exclude(pk=self.instance.pk)
        if existing_profiles.exists():
            raise forms.ValidationError("A profile already uses this roll number.")
        try:
            validate_student_login_username(
                roll_number,
                exclude_user_id=self.instance.user_id,
            )
        except forms.ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        return roll_number


class LearningBatchAdminForm(forms.ModelForm):
    created_by_admin = forms.ModelChoiceField(
        label="Created by admin",
        queryset=get_user_model().objects.filter(is_staff=True).order_by("username"),
    )

    class Meta:
        model = LearningBatch
        fields = ("name", "created_by_admin", "members")
        widgets = {
            "members": forms.CheckboxSelectMultiple,
        }


@admin.register(StudentRegistrationRequest)
class StudentRegistrationRequestAdmin(admin.ModelAdmin):
    change_list_template = (
        "admin/matching/studentregistrationrequest/change_list.html"
    )
    list_display = ("name", "email", "status", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("name", "email")
    readonly_fields = ("status", "created_at", "reviewed_at")
    fields = (
        "name",
        "email",
        "teach_skills",
        "learn_skills",
        "status",
        "created_at",
        "reviewed_at",
    )
    actions = ("approve_requests", "reject_requests")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "status__exact" not in request.GET:
            return queryset.filter(
                status=StudentRegistrationRequest.Status.PENDING
            )
        return queryset

    @admin.action(description="Approve selected registration requests")
    def approve_requests(self, request, queryset):
        approved_count = 0
        login_credentials = []
        for registration_request in queryset.filter(
            status=StudentRegistrationRequest.Status.PENDING
        ):
            form = StudentForm(
                data={
                    "name": registration_request.name,
                    "email": registration_request.email,
                    "teach_skills": ", ".join(
                        registration_request.teach_skills
                    ),
                    "learn_skills": ", ".join(
                        registration_request.learn_skills
                    ),
                }
            )
            if not form.is_valid():
                messages.error(
                    request,
                    f"{registration_request.email} could not be approved: "
                    f"{form.errors.as_text()}",
                )
                continue

            with transaction.atomic():
                student = form.save()
                registration_request.status = (
                    StudentRegistrationRequest.Status.APPROVED
                )
                registration_request.reviewed_at = timezone.now()
                registration_request.save(
                    update_fields=("status", "reviewed_at")
                )
            login_credentials.append(
                f"{student.roll_number} / {form.generated_password}"
            )
            approved_count += 1

        if approved_count:
            self.message_user(
                request,
                f"Approved {approved_count} registration request(s). "
                "Student login credentials (username / initial six-digit password; shown once): "
                + "; ".join(login_credentials),
                messages.SUCCESS,
            )
        if not approved_count and not queryset.filter(
            status=StudentRegistrationRequest.Status.PENDING
        ).exists():
            self.message_user(
                request,
                "No pending registration requests were selected.",
                messages.WARNING,
            )

    @admin.action(description="Reject selected registration requests")
    def reject_requests(self, request, queryset):
        pending_requests = queryset.filter(
            status=StudentRegistrationRequest.Status.PENDING
        )
        rejected_count = pending_requests.update(
            status=StudentRegistrationRequest.Status.REJECTED,
            reviewed_at=timezone.now(),
        )
        if rejected_count:
            self.message_user(
                request,
                f"Rejected {rejected_count} registration request(s).",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No pending registration requests were selected.",
                messages.WARNING,
            )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    exclude = ("user", "login_code")
    list_display = ("name", "roll_number", "email", "account_username", "created_at")
    search_fields = ("name", "roll_number", "email", "user__username")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            sync_student_login_username(obj)
            return

        password = create_student_login(obj)
        self.message_user(
            request,
            f"Student login created. Username: {obj.roll_number}; "
            f"initial six-digit password: {password}. "
            "This password is shown once.",
            messages.SUCCESS,
        )

    @admin.display(description="Student login")
    def account_username(self, obj):
        return obj.user.get_username() if obj.user_id else "Not linked"


@admin.register(StudentLoginCode)
class StudentLoginCodeAdmin(admin.ModelAdmin):
    list_display = ("name", "roll_number", "email", "displayed_login_code")
    list_display_links = None
    search_fields = ("name", "roll_number", "email")
    actions = ("generate_login_codes",)

    @admin.display(description="Six-digit login code")
    def displayed_login_code(self, obj):
        return obj.login_code or "Not generated"

    @admin.action(description="Generate/reset six-digit codes for selected students")
    def generate_login_codes(self, request, queryset):
        generated_count = 0
        for student in queryset:
            try:
                with transaction.atomic():
                    reset_student_login_code(student)
            except forms.ValidationError as error:
                self.message_user(
                    request,
                    f"{student.name} ({student.roll_number}) could not receive a login code: "
                    f"{error.messages}",
                    messages.ERROR,
                )
                continue
            generated_count += 1

        if generated_count:
            self.message_user(
                request,
                f"Generated login codes for {generated_count} student(s). "
                "The codes are shown in this list.",
                messages.SUCCESS,
            )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LearningBatch)
class LearningBatchAdmin(admin.ModelAdmin):
    form = LearningBatchAdminForm
    list_display = ("name", "creator", "created_at")
    search_fields = (
        "name",
        "created_by_admin__username",
        "created_by_student__name",
    )
    @admin.display(description="Created by")
    def creator(self, obj):
        if obj.created_by_admin_id:
            return obj.created_by_admin.get_username()
        if obj.created_by_student_id:
            return f"{obj.created_by_student.name} (legacy)"
        return "—"


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "location",
        "is_active",
        "application_deadline",
        "renewed_from_job",
    )
    list_filter = ("is_active",)
    search_fields = ("title", "company", "location", "required_skills")
    fieldsets = (
        (None, {"fields": ("title", "company", "location", "description")}),
        (
            "Applications",
            {"fields": ("required_skills", "application_deadline", "is_active")},
        ),
    )

    @admin.display(description="Renewed from")
    def renewed_from_job(self, obj):
        return obj.renewed_from or "—"


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "job", "status", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = ("student__name", "student__email", "job__title", "job__company")
    fields = ("student", "job", "status", "resume_download", "cover_note", "applied_at")
    readonly_fields = ("student", "job", "resume_download", "cover_note", "applied_at")

    @admin.display(description="Resume")
    def resume_download(self, obj):
        if not obj or not obj.resume:
            return "No resume uploaded"
        url = reverse("download-application-resume", args=[obj.pk])
        return format_html('<a href="{}">Download private resume</a>', url)
