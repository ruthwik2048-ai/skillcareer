

import django.db.models.deletion
import matching.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0011_studentregistrationrequest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('company', models.CharField(max_length=150)),
                ('location', models.CharField(blank=True, max_length=150)),
                ('description', models.TextField()),
                ('required_skills', models.CharField(blank=True, help_text='Comma-separated skills used to recommend this job.', max_length=500)),
                ('application_deadline', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at', 'title'],
            },
        ),
        migrations.AddField(
            model_name='student',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_profile', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='JobApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resume', models.FileField(upload_to=matching.models.application_resume_path)),
                ('cover_note', models.TextField(blank=True, max_length=3000)),
                ('status', models.CharField(choices=[('submitted', 'Submitted'), ('reviewing', 'Under review'), ('interview', 'Interview'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='submitted', max_length=12)),
                ('applied_at', models.DateTimeField(auto_now_add=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='matching.job')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_applications', to='matching.student')),
            ],
            options={
                'ordering': ['-applied_at'],
                'constraints': [models.UniqueConstraint(fields=('student', 'job'), name='unique_job_application_per_student')],
            },
        ),
    ]
