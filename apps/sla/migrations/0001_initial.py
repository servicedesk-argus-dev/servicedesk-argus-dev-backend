# Generated manually for Argus Service Desk SLA definitions.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SLADefinition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("applies_to", models.CharField(choices=[("INCIDENT", "Incident"), ("CHANGE", "Change")], default="INCIDENT", max_length=20)),
                ("priority", models.CharField(choices=[("P1", "P1 - Critical"), ("P2", "P2 - High"), ("P3", "P3 - Moderate"), ("P4", "P4 - Low")], max_length=2)),
                ("response_time_minutes", models.PositiveIntegerField(default=60)),
                ("resolution_time_minutes", models.PositiveIntegerField(default=1440)),
                ("business_hours_only", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("start_condition", models.TextField(default="Task is active and priority matches the SLA definition.")),
                ("pause_condition", models.TextField(default="Incident state is On Hold or change state is Approval/Scheduled.")),
                ("stop_condition", models.TextField(default="Task is Resolved, Closed, or Cancelled.")),
                ("reset_condition", models.TextField(default="Priority, impact, urgency, risk, or planned dates change.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sla_definitions", to="organizations.organization")),
            ],
            options={
                "db_table": "sla_definitions",
                "ordering": ["applies_to", "priority"],
            },
        ),
        migrations.AddConstraint(
            model_name="sladefinition",
            constraint=models.UniqueConstraint(fields=("organization", "applies_to", "priority"), name="uniq_sla_definition_org_applies_priority"),
        ),
    ]
