from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from matching.models import Job, add_one_calendar_month


class Command(BaseCommand):
    help = "Create a one-time renewed copy of each expired active job."

    def handle(self, *args, **options):
        today = timezone.localdate()
        expired_job_ids = list(
            Job.objects.filter(
                is_active=True,
                application_deadline__lt=today,
                renewed_from__isnull=True,
                renewed_job__isnull=True,
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        created_count = 0

        for job_id in expired_job_ids:
            with transaction.atomic():
                job = (
                    Job.objects.select_for_update()
                    .filter(
                        pk=job_id,
                        is_active=True,
                        application_deadline__lt=today,
                        renewed_from__isnull=True,
                        renewed_job__isnull=True,
                    )
                    .first()
                )
                if job is None:
                    continue

                Job.objects.create(
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    description=job.description,
                    required_skills=job.required_skills,
                    application_deadline=add_one_calendar_month(today),
                    is_active=True,
                    renewed_from=job,
                )
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created {created_count} renewed job(s).")
        )
