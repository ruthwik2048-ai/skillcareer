import calendar
from datetime import date

import django.db.models.deletion
import matching.models
from django.db import migrations, models
from django.utils import timezone


def backfill_job_deadlines(apps, schema_editor):
    Job = apps.get_model("matching", "Job")
    today = timezone.localdate()
    month_index = today.month
    year = today.year + (month_index // 12)
    month = month_index % 12 + 1
    deadline = date(
        year,
        month,
        min(today.day, calendar.monthrange(year, month)[1]),
    )
    Job.objects.filter(application_deadline__isnull=True).update(
        application_deadline=deadline
    )


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0013_studentlogincode_student_login_code"),
    ]

    operations = [
        migrations.RunPython(
            backfill_job_deadlines,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="job",
            name="application_deadline",
            field=models.DateField(default=matching.models.default_job_deadline),
        ),
        migrations.AddField(
            model_name="job",
            name="renewed_from",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="renewed_job",
                to="matching.job",
            ),
        ),
    ]
