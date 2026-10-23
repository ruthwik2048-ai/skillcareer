import uuid
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.db import transaction

from .models import JobApplication, LearningBatch, Student, StudentRegistrationRequest
from .services import (
    create_student_login,
    sync_student_login_username,
    validate_student_login_username,
)


class StudentForm(forms.ModelForm):
    roll_number = forms.CharField(
        label="Roll number",
        max_length=30,
        help_text="Enter your unique student roll number.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    teach_skills = forms.CharField(
        label="Skills you can teach",
        required=False,
        help_text="Separate skills with commas.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    learn_skills = forms.CharField(
        label="Skills you want to learn",
        required=False,
        help_text="Separate skills with commas.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = Student
        fields = ["name", "email", "roll_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generated_password = None
        if self.instance.pk is None:
            self.fields.pop("roll_number")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing_profiles = Student.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing_profiles = existing_profiles.exclude(pk=self.instance.pk)
        if existing_profiles.exists():
            raise forms.ValidationError(
                "A profile already uses this email. Contact an administrator if you need help updating it."
            )
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

    def clean_teach_skills(self):
        return self._parse_skills(self.cleaned_data["teach_skills"])

    def clean_learn_skills(self):
        return self._parse_skills(self.cleaned_data["learn_skills"])

    @staticmethod
    def _parse_skills(value):
        return [skill.strip().lower() for skill in value.split(",") if skill.strip()]

    def save(self, commit=True):
        student = super().save(commit=False)
        student.teach_skills = self.cleaned_data["teach_skills"]
        student.learn_skills = self.cleaned_data["learn_skills"]
        if commit:
            if student.pk is None:
                with transaction.atomic():
                    student.roll_number = f"PENDING-{uuid.uuid4().hex}"
                    student.save()

                    number = student.pk
                    roll_number = f"SW{number:06d}"
                    user_model = get_user_model()
                    username_field = user_model.USERNAME_FIELD
                    while (
                        Student.objects.filter(
                            roll_number__iexact=roll_number
                        )
                        .exclude(pk=student.pk)
                        .exists()
                        or user_model._default_manager.filter(
                            **{f"{username_field}__iexact": roll_number}
                        ).exists()
                    ):
                        number += 1
                        roll_number = f"SW{number:06d}"

                    student.roll_number = roll_number
                    student.save(update_fields=["roll_number"])
                    self.generated_password = create_student_login(student)
            else:
                with transaction.atomic():
                    student.save()
                    sync_student_login_username(student)
        return student


class StudentRegistrationRequestForm(forms.ModelForm):
    teach_skills = forms.CharField(
        label="Skills you can teach",
        required=False,
        help_text="Separate skills with commas.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    learn_skills = forms.CharField(
        label="Skills you want to learn",
        required=False,
        help_text="Separate skills with commas.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = StudentRegistrationRequest
        fields = ["name", "email", "teach_skills", "learn_skills"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Student.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "A student profile already uses this email."
            )
        if StudentRegistrationRequest.objects.filter(
            email__iexact=email,
            status=StudentRegistrationRequest.Status.PENDING,
        ).exists():
            raise forms.ValidationError(
                "A registration request for this email is already awaiting review."
            )
        return email

    def clean_teach_skills(self):
        return StudentForm._parse_skills(self.cleaned_data["teach_skills"])

    def clean_learn_skills(self):
        return StudentForm._parse_skills(self.cleaned_data["learn_skills"])


class StudentAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "Enter the correct roll-number username and password. "
            "Username matching ignores letter case; passwords are case-sensitive."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Roll number (username)"
        self.fields["username"].widget.attrs["placeholder"] = "e.g. SW000001"
        self.fields["password"].widget.attrs["data-password-visibility"] = "true"

    def clean_username(self):
        username = self.cleaned_data["username"]
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        matches = list(
            user_model._default_manager.filter(
                **{f"{username_field}__iexact": username}
            )[:2]
        )
        if len(matches) == 1:
            return getattr(matches[0], username_field)
        return username


class AdminPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        user_model = get_user_model()
        email_field = user_model.get_email_field_name()
        users = user_model._default_manager.filter(
            **{
                f"{email_field}__iexact": email,
                "is_active": True,
                "is_staff": True,
            }
        )
        return (
            user
            for user in users
            if user.has_usable_password()
        )


class LearningBatchForm(forms.ModelForm):
    class Meta:
        model = LearningBatch
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Python study group"}),
        }


class LearningBatchUpdateForm(forms.ModelForm):
    class Meta:
        model = LearningBatch
        fields = ["name", "members"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Python study group"}),
            "members": forms.CheckboxSelectMultiple(),
        }


class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ["resume", "cover_note"]
        widgets = {
            "resume": forms.ClearableFileInput(
                attrs={"accept": ".pdf,application/pdf"}
            ),
            "cover_note": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Tell the employer why you are a good fit (optional).",
                }
            ),
        }

    def clean_resume(self):
        resume = self.cleaned_data["resume"]
        if resume.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Resume files must be 5 MB or smaller.")
        if Path(resume.name).suffix.casefold() != ".pdf":
            raise forms.ValidationError("Upload your resume as a PDF file.")
        if resume.read(5) != b"%PDF-":
            raise forms.ValidationError("The uploaded file is not a valid PDF.")
        resume.seek(0)
        return resume
