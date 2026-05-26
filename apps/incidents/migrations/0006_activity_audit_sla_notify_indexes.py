from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0005_incident_controlled_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="actor_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="activity",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="incident",
            name="sla_notified_thresholds",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(fields=["organization", "state", "created_at"], name="incidents_org_state_created_idx"),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(
                fields=["organization", "priority", "created_at"],
                name="incidents_org_pri_created_idx",
            ),
        ),
    ]
