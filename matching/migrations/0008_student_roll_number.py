from django.db import migrations, models


def assign_existing_roll_numbers(apps, schema_editor):
    Student = apps.get_model("matching", "Student")
    for student in Student.objects.order_by("pk").iterator():
        student.roll_number = f"SW{student.pk:06d}"
        student.save(update_fields=["roll_number"])


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0007_delete_mobilelogincode"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="roll_number",
            field=models.CharField(max_length=30, null=True),
        ),
        migrations.RunPython(
            assign_existing_roll_numbers,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="student",
            name="roll_number",
            field=models.CharField(max_length=30, unique=True),
        ),
    ]
