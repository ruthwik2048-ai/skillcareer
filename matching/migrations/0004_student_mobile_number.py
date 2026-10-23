from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0003_delete_emaillogintoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="mobile_number",
            field=models.CharField(blank=True, max_length=16, null=True, unique=True),
        ),
    ]
