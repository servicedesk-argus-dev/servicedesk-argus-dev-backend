import uuid
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from apps.organizations.models import Organization

class Workflow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='workflows')
    
    # The model this workflow applies to (e.g., Incident, Change)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflows"

    def __str__(self):
        return self.name

    @property
    def initial_state(self):
        return self.states.filter(is_initial=True).first()

class WorkflowState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='states')
    name = models.CharField(max_length=100)
    is_initial = models.BooleanField(default=False)
    is_final = models.BooleanField(default=False)
    
    color = models.CharField(max_length=20, default="#000000")
    
    class Meta:
        db_table = "workflow_states"
        unique_together = ['workflow', 'name']

class WorkflowTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='transitions')
    from_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='outgoing_transitions')
    to_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='incoming_transitions')
    
    name = models.CharField(max_length=100)
    required_permission = models.CharField(max_length=100, blank=True, null=True)
    
    # Conditions for transition (JSON DSL)
    conditions = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = "workflow_transitions"


class WorkflowAction(models.Model):
    class ActionType(models.TextChoices):
        CREATE_TASK = "CREATE_TASK", "Create Catalog Task"
        SEND_NOTIFICATION = "SEND_NOTIFICATION", "Send Notification"
        UPDATE_FIELD = "UPDATE_FIELD", "Update Record Field"
        WEBHOOK = "WEBHOOK", "Trigger Webhook"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='actions')
    name = models.CharField(max_length=100)
    
    type = models.CharField(max_length=50, choices=ActionType.choices)
    params = models.JSONField(default=dict, blank=True)
    
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = "workflow_actions"
        ordering = ['order']


class WorkflowExecution(models.Model):
    """Tracks the history of a workflow on a specific record."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE)
    
    # Generic link to the target record (Incident, RITM, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    current_state = models.ForeignKey(WorkflowState, on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflow_executions"
        unique_together = ['content_type', 'object_id', 'workflow']
