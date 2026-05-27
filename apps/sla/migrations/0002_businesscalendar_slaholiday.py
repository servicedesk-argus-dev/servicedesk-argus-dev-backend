import uuid
from datetime import time

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
        ("sla", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessCalendar",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("timezone_name", models.CharField(default="UTC", max_length=64)),
                ("workday_start", models.TimeField(default=time(9, 0))),
                ("workday_end", models.TimeField(default=time(17, 0))),
                ("work_weekdays", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_calendar",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"db_table": "sla_business_calendars"},
        ),
        migrations.CreateModel(
            name="SLAHoliday",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("date", models.DateField()),
                ("name", models.CharField(blank=True, max_length=120)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sla_holidays",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "sla_holidays",
            },
        ),
        migrations.AddConstraint(
            model_name="slaholiday",
            constraint=models.UniqueConstraint(fields=("organization", "date"), name="uniq_sla_holiday_org_date"),
        ),
    ]
