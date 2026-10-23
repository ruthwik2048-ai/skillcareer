import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0009_remove_student_mobile_number"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="learningbatch",
            old_name="created_by",
            new_name="created_by_student",
        ),
        migrations.AlterField(
            model_name="learningbatch",
            name="created_by_student",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_batches",
                to="matching.student",
            ),
        ),
        migrations.AddField(
            model_name="learningbatch",
            name="created_by_admin",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_learning_batches",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created by admin",
            ),
        ),
    ]
