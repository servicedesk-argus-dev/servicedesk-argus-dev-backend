import uuid
from django.db import models
from apps.organizations.models import Organization


class Alert(models.Model):
    class Severity(models.TextChoices):
        CRITICAL = "CRITICAL", "Critical"
        WARNING = "WARNING", "Warning"
        INFO = "INFO", "Info"

    class Status(models.TextChoices):
        FIRING = "FIRING", "Firing"
        RESOLVED = "RESOLVED", "Resolved"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        SILENCED = "SILENCED", "Silenced"

    class Source(models.TextChoices):
        PROMETHEUS = "PROMETHEUS", "Prometheus"
        GRAFANA = "GRAFANA", "Grafana"
        CUSTOM = "CUSTOM", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert_id = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FIRING, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CUSTOM)
    
    description = models.TextField(blank=True, null=True)
    metric = models.CharField(max_length=255, blank=True, null=True)
    current_value = models.CharField(max_length=255, blank=True, null=True)
    threshold = models.CharField(max_length=255, blank=True, null=True)
    labels = models.JSONField(blank=True, null=True)
    annotations = models.JSONField(blank=True, null=True)

    config_item = models.ForeignKey(
        'assets.ConfigurationItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts',
    )
    incident = models.ForeignKey('incidents.Incident', on_delete=models.SET_NULL, null=True, blank=True, related_name='related_alerts')

    fired_at = models.DateTimeField(db_index=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    silence_until = models.DateTimeField(blank=True, null=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='alerts')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "alerts"
        ordering = ["-fired_at"]
        indexes = [
            models.Index(fields=["status", "severity"]),
            models.Index(fields=["fired_at"]),
        ]

    def __str__(self):
        return f"{self.alert_id} - {self.name}"
