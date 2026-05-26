import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization

User = get_user_model()


class Problem(models.Model):
    class State(models.TextChoices):
        NEW = "NEW", "New"
        INVESTIGATION = "INVESTIGATION", "Investigation"
        RCA_IN_PROGRESS = "RCA_IN_PROGRESS", "RCA In Progress"
        KNOWN_ERROR = "KNOWN_ERROR", "Known Error"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        P1 = "P1", "P1 - Critical"
        P2 = "P2", "P2 - High"
        P3 = "P3", "P3 - Medium"
        P4 = "P4", "P4 - Low"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    short_description = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEW, db_index=True)
    priority = models.CharField(max_length=2, choices=Priority.choices, default=Priority.P3, db_index=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    
    assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_problems')
    assignment_group = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_problems')
    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='created_problems')
    
    root_cause = models.TextField(blank=True, null=True)
    root_cause_analysis = models.JSONField(blank=True, null=True)
    workaround = models.TextField(blank=True, null=True)
    workaround_effective = models.BooleanField(default=False)
    permanent_fix = models.TextField(blank=True, null=True)
    fix_implemented = models.BooleanField(default=False)
    
    related_change = models.ForeignKey('changes.Change', on_delete=models.SET_NULL, null=True, blank=True, related_name='related_problems')
    is_known_error = models.BooleanField(default=False)
    known_error_id = models.CharField(max_length=50, blank=True, null=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='problems')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "problems"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["state", "priority"]),
        ]

    def __str__(self):
        return f"{self.number} - {self.short_description}"


class ProblemTask(models.Model):
    class State(models.TextChoices):
        NEW = "NEW", "New"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        P1 = "P1", "P1 - Critical"
        P2 = "P2", "P2 - High"
        P3 = "P3", "P3 - Medium"
        P4 = "P4", "P4 - Low"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='tasks')
    
    short_description = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEW)
    priority = models.CharField(max_length=2, choices=Priority.choices, default=Priority.P3)
    
    assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_problem_tasks')
    assignment_group = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_problem_tasks')
    
    due_date = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='problem_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "problem_tasks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} - {self.short_description}"
