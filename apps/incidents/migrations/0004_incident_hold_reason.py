from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0003_incidentchange_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="hold_reason",
            field=models.TextField(blank=True, null=True),
        ),
    ]

