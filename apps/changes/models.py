import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization

User = get_user_model()


class Change(models.Model):
    class Type(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        STANDARD = "STANDARD", "Standard"
        EMERGENCY = "EMERGENCY", "Emergency"

    class State(models.TextChoices):
        NEW = "NEW", "New"
        ASSESSMENT = "ASSESSMENT", "Assessment"
        APPROVAL = "APPROVAL", "Approval"
        SCHEDULED = "SCHEDULED", "Scheduled"
        IMPLEMENTING = "IMPLEMENTING", "Implementing"
        REVIEW = "REVIEW", "Review"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    class RiskLevel(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class ClosureCode(models.TextChoices):
        SUCCESSFUL = "SUCCESSFUL", "Successful"
        FAILED = "FAILED", "Failed"
        PARTIAL = "PARTIAL", "Partial"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    short_description = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.NORMAL)
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEW, db_index=True)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.MEDIUM)
    category = models.CharField(max_length=100, blank=True, null=True)
    
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_changes')
    assignment_group = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_changes')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_changes')
    
    justification = models.TextField(blank=True, null=True)
    implementation_plan = models.TextField(blank=True, null=True)
    rollback_plan = models.TextField(blank=True, null=True)
    test_plan = models.TextField(blank=True, null=True)
    communication_plan = models.TextField(blank=True, null=True)
    
    planned_start_date = models.DateTimeField(blank=True, null=True)
    planned_end_date = models.DateTimeField(blank=True, null=True)
    actual_start_date = models.DateTimeField(blank=True, null=True)
    actual_end_date = models.DateTimeField(blank=True, null=True)
    
    affected_services = models.TextField(blank=True, null=True)
    downtime = models.IntegerField(blank=True, null=True)  # in minutes
    user_impact = models.TextField(blank=True, null=True)
    
    git_repo_url = models.URLField(blank=True, null=True)
    git_branch = models.CharField(max_length=255, blank=True, null=True)
    git_commit_hash = models.CharField(max_length=255, blank=True, null=True)
    pull_request_url = models.URLField(blank=True, null=True)
    
    review_notes = models.TextField(blank=True, null=True)
    closure_code = models.CharField(max_length=20, choices=ClosureCode.choices, blank=True, null=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='changes')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "changes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["state", "type"]),
            models.Index(fields=["planned_start_date"]),
        ]

    def __str__(self):
        return f"{self.number} - {self.short_description}"


class Approval(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approvals')
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    comments = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approvals"
        ordering = ["-created_at"]


class ChangeCI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    change = models.ForeignKey('changes.Change', on_delete=models.CASCADE, related_name='affected_cis')
    config_item = models.ForeignKey('assets.ConfigurationItem', on_delete=models.CASCADE, related_name='affected_by_changes')
    impact_type = models.CharField(max_length=50, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "change_cis"


class MaintenanceWindow(models.Model):
    class Type(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Maintenance Window"
        BLACKOUT = "BLACKOUT", "Blackout Period"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.MAINTENANCE)
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='maintenance_windows')
    
    # Optional scope
    affected_cis = models.ManyToManyField('assets.ConfigurationItem', blank=True, related_name='maintenance_windows')
    affected_groups = models.ManyToManyField('teams.Team', blank=True, related_name='maintenance_windows')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "maintenance_windows"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.type})"


class RiskAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    change = models.OneToOneField(Change, on_delete=models.CASCADE, related_name='risk_assessment')
    
    # JSON structure for questions and answers
    # e.g., [{"question": "Is there redundancy?", "answer": "No", "weight": 10}]
    assessment_data = models.JSONField(default=dict)
    calculated_score = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "change_risk_assessments"
