import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization

User = get_user_model()


class Notification(models.Model):
    class Type(models.TextChoices):
        INCIDENT = "INCIDENT", "Incident"
        CHANGE = "CHANGE", "Change"
        PROBLEM = "PROBLEM", "Problem"
        ALERT = "ALERT", "Alert"
        SLA = "SLA", "SLA"
        SYSTEM = "SYSTEM", "System"

    class Channel(models.TextChoices):
        WEB = "WEB", "Web"
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"
        SLACK = "SLACK", "Slack"
        VOICE = "VOICE", "Voice"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SYSTEM)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.URLField(blank=True, null=True)
    
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WEB)
    
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='notifications')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"

class NotificationTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='notification_templates')
    name = models.CharField(max_length=255)
    subject_template = models.CharField(max_length=255, blank=True)
    body_template = models.TextField()
    
    type = models.CharField(max_length=20, choices=Notification.Type.choices)
    channel = models.CharField(max_length=20, choices=Notification.Channel.choices)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        unique_together = ['organization', 'name']
