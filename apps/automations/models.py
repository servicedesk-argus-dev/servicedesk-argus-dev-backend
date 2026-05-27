import uuid
from django.db import models
from apps.organizations.models import Organization

class AutomationRule(models.Model):
    class Trigger(models.TextChoices):
        ON_CREATE = "ON_CREATE", "On Create"
        ON_UPDATE = "ON_UPDATE", "On Update"
        ON_DELETE = "ON_DELETE", "On Delete"
        ON_SLA_BREACH = "ON_SLA_BREACH", "On SLA Breach"
        ON_TIMER = "ON_TIMER", "On Timer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='automation_rules')
    
    trigger = models.CharField(max_length=20, choices=Trigger.choices)
    target_model = models.CharField(max_length=100) # e.g. 'incidents.Incident'
    
    # Conditions (JSON DSL)
    conditions = models.JSONField(default=list, blank=True)
    
    # Actions (JSON DSL)
    actions = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "automation_rules"
        ordering = ["priority", "name"]

    def __str__(self):
        return self.name
