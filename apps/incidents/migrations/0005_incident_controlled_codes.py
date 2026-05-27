from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0004_incident_hold_reason"),
    ]

    operations = [
        migrations.AlterField(
            model_name="incident",
            name="hold_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("AWAITING_USER", "Awaiting User"),
                    ("AWAITING_VENDOR", "Awaiting Vendor"),
                    ("AWAITING_CHANGE_WINDOW", "Awaiting Change Window"),
                    ("AWAITING_DEPENDENCY", "Awaiting Dependency"),
                    ("MONITORING", "Monitoring"),
                    ("OTHER", "Other"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="incident",
            name="resolution_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("WORKAROUND_APPLIED", "Workaround Applied"),
                    ("PERMANENT_FIX", "Permanent Fix"),
                    ("CONFIG_CHANGE", "Configuration Change"),
                    ("SERVICE_RESTART", "Service Restart"),
                    ("DUPLICATE_INCIDENT", "Duplicate Incident"),
                    ("USER_ERROR", "User Error"),
                    ("NO_ISSUE_FOUND", "No Issue Found"),
                    ("VENDOR_FIX", "Vendor Fix"),
                ],
                max_length=40,
                null=True,
            ),
        ),
    ]

