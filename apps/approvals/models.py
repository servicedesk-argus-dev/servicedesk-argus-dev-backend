import uuid
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from apps.organizations.models import Organization

class ApprovalRequest(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='approval_requests')
    
    # The record needing approval
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "approval_requests"
        ordering = ["-created_at"]

class Approver(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ApprovalRequest, on_delete=models.CASCADE, related_name='approvers')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='pending_approvals')
    
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    comments = models.TextField(blank=True, null=True)
    
    actioned_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = "approvers"
        unique_together = ['request', 'user']
