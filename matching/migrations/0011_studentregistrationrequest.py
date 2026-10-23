from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0010_learningbatch_admin_creator'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentRegistrationRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('teach_skills', models.JSONField(blank=True, default=list)),
                ('learn_skills', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['status', '-created_at', 'name'],
            },
        ),
    ]
