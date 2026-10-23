from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetView
from django.urls import reverse_lazy
from django.utils.http import urlsafe_base64_decode

from .forms import AdminPasswordResetForm


class AdminPasswordResetView(PasswordResetView):
    form_class = AdminPasswordResetForm
    success_url = reverse_lazy("admin_password_reset_done")


class AdminPasswordResetConfirmView(PasswordResetConfirmView):
    def get_user(self, uidb64):
        try:
            user_id = urlsafe_base64_decode(uidb64).decode()
            return get_user_model()._default_manager.get(
                pk=user_id,
                is_staff=True,
                is_active=True,
            )
        except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
            return None
