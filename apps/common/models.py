import uuid
from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", 
        on_delete=models.CASCADE, 
        related_name="audit_logs",
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="audit_logs"
    )
    action = models.CharField(max_length=100) # e.g., "LOGIN", "PASSWORD_RESET", "USER_INVITED"
    resource_type = models.CharField(max_length=100) # e.g., "USER", "INCIDENT", "SLA"
    resource_id = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Payload for deep auditing
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]
