from django.urls import path

from . import views


urlpatterns = [
    path("", views.student_list, name="student-list"),
    path("register/", views.request_student_registration, name="register-student"),
    path("jobs/", views.job_list, name="job-list"),
    path(
        "students/<int:student_id>/jobs/",
        views.job_list,
        name="student-jobs",
    ),
    path("jobs/<int:job_id>/apply/", views.apply_for_job, name="apply-for-job"),
    path("student/login/", views.student_login, name="student-login"),
    path("student/logout/", views.student_logout, name="student-logout"),
    path("student/dashboard/", views.student_dashboard, name="student-dashboard"),
    path(
        "student/applications/<int:application_id>/resume/",
        views.download_application_resume,
        name="download-application-resume",
    ),
    path("students/<int:student_id>/delete/", views.delete_student, name="delete-student"),
    path("students/<int:student_id>/edit/", views.update_student, name="update-student"),
    path("students/<int:student_id>/matches/", views.student_matches, name="student-matches"),
    path("batches/", views.learning_batches, name="learning-batches"),
    path("batches/<int:batch_id>/edit/", views.update_learning_batch, name="update-learning-batch"),
]
