from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0008_student_roll_number"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="student",
            name="mobile_number",
        ),
    ]
