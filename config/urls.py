from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy

from matching.auth_views import (
    AdminPasswordResetConfirmView,
    AdminPasswordResetView,
)


urlpatterns = [
    path(
        "admin/password_reset/",
        AdminPasswordResetView.as_view(),
        name="admin_password_reset",
    ),
    path(
        "admin/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="admin_password_reset_done",
    ),
    path(
        "admin/reset/<uidb64>/<token>/",
        AdminPasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("admin_password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "admin/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="admin_password_reset_complete",
    ),
    path("admin/", admin.site.urls),
    path("", include("matching.urls")),
]
