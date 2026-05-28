import uuid
from django.db import models
from django.contrib.auth import get_user_model
# pyrefly: ignore [missing-import]
from apps.organizations.models import Organization
from apps.accounts.models import User as CustomUser

User = get_user_model()


class Incident(models.Model):
    class State(models.TextChoices):
        NEW = "NEW", "New"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        ON_HOLD = "ON_HOLD", "On Hold"
        ESCALATED = "ESCALATED", "Escalated"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Impact(models.TextChoices):
        ENTERPRISE = "ENTERPRISE", "Enterprise"
        DEPARTMENT = "DEPARTMENT", "Department"
        TEAM = "TEAM", "Team"
        INDIVIDUAL = "INDIVIDUAL", "Individual"

    class Urgency(models.TextChoices):
        CRITICAL = "CRITICAL", "Critical"
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class Priority(models.TextChoices):
        P1 = "P1", "P1 - Critical"
        P2 = "P2", "P2 - High"
        P3 = "P3", "P3 - Medium"
        P4 = "P4", "P4 - Low"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        PROMETHEUS = "PROMETHEUS", "Prometheus"
        GRAFANA = "GRAFANA", "Grafana"
        API = "API", "API"
        EMAIL = "EMAIL", "Email"
        VOICE = "VOICE", "Voice"
        SLACK = "SLACK", "Slack"

    class HoldReason(models.TextChoices):
        AWAITING_USER = "AWAITING_USER", "Awaiting User"
        AWAITING_VENDOR = "AWAITING_VENDOR", "Awaiting Vendor"
        AWAITING_CHANGE_WINDOW = "AWAITING_CHANGE_WINDOW", "Awaiting Change Window"
        AWAITING_DEPENDENCY = "AWAITING_DEPENDENCY", "Awaiting Dependency"
        MONITORING = "MONITORING", "Monitoring"
        OTHER = "OTHER", "Other"

    class ResolutionCode(models.TextChoices):
        WORKAROUND_APPLIED = "WORKAROUND_APPLIED", "Workaround Applied"
        PERMANENT_FIX = "PERMANENT_FIX", "Permanent Fix"
        CONFIG_CHANGE = "CONFIG_CHANGE", "Configuration Change"
        SERVICE_RESTART = "SERVICE_RESTART", "Service Restart"
        DUPLICATE_INCIDENT = "DUPLICATE_INCIDENT", "Duplicate Incident"
        USER_ERROR = "USER_ERROR", "User Error"
        NO_ISSUE_FOUND = "NO_ISSUE_FOUND", "No Issue Found"
        VENDOR_FIX = "VENDOR_FIX", "Vendor Fix"

    class MajorIncidentState(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        CANCELED = "CANCELED", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    short_description = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEW, db_index=True)
    impact = models.CharField(max_length=20, choices=Impact.choices, default=Impact.TEAM)
    urgency = models.CharField(max_length=20, choices=Urgency.choices, default=Urgency.MEDIUM)
    priority = models.CharField(max_length=2, choices=Priority.choices, default=Priority.P3, db_index=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    site = models.ForeignKey(
        'assets.AssetSite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents'
    )
    location = models.CharField(max_length=255, blank=True, null=True)
    
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_incidents')

    @property
    def child_status_summary(self):
        """Get aggregated status of all child incidents"""
        if not self.child_incidents.exists():
            return None
            
        children = self.child_incidents.all()
        total = children.count()
        
        status_counts = {
            'total': total,
            'new': children.filter(state=self.State.NEW).count(),
            'in_progress': children.filter(state=self.State.IN_PROGRESS).count(),
            'on_hold': children.filter(state=self.State.ON_HOLD).count(),
            'escalated': children.filter(state=self.State.ESCALATED).count(),
            'resolved': children.filter(state=self.State.RESOLVED).count(),
            'closed': children.filter(state=self.State.CLOSED).count(),
            'cancelled': children.filter(state=self.State.CANCELLED).count(),
        }
        
        # Calculate completion percentage
        completed = status_counts['resolved'] + status_counts['closed'] + status_counts['cancelled']
        status_counts['completion_percentage'] = round((completed / total) * 100) if total > 0 else 0
        
        return status_counts

    @property
    def hierarchy_level(self):
        """Get the depth level in the incident hierarchy"""
        level = 0
        current = self.parent
        while current and level < 10:  # Prevent infinite loops
            level += 1
            current = current.parent
        return level

    @property
    def root_parent(self):
        """Get the root parent incident"""
        current = self
        while current.parent and current != current.parent:
            current = current.parent
        return current if current != self else None
    is_major_incident = models.BooleanField(default=False, db_index=True)
    major_incident_state = models.CharField(max_length=20, choices=MajorIncidentState.choices, blank=True, null=True)
    major_incident_notes = models.TextField(blank=True, null=True)

    assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    assignment_group = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    config_item = models.ForeignKey(
        'assets.ConfigurationItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
    )
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_requested_for'
    )
    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='created_incidents')
        
    sla_breached = models.BooleanField(default=False, db_index=True)
    sla_notified_thresholds = models.JSONField(default=list, blank=True)
    response_time = models.DurationField(blank=True, null=True)
    resolution_time = models.DurationField(blank=True, null=True)
    sla_target_response = models.DurationField(blank=True, null=True)
    sla_target_resolution = models.DurationField(blank=True, null=True)
    
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    source_alert_id = models.CharField(max_length=255, blank=True, null=True)
    source_alert_name = models.CharField(max_length=255, blank=True, null=True)
    
    resolved_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    hold_reason = models.CharField(max_length=40, choices=HoldReason.choices, blank=True, null=True)
    resolution_code = models.CharField(max_length=40, choices=ResolutionCode.choices, blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='incidents')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "incidents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["state", "priority"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["organization", "state", "created_at"]),
            models.Index(fields=["organization", "priority", "created_at"]),
            models.Index(fields=["organization", "source_alert_id", "state"], name="incidents_organiz_b99a3c_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.short_description}"


class WorkNote(models.Model):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        AI = "AI", "AI"
        SYSTEM = "SYSTEM", "System"
        SLACK = "SLACK", "Slack"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField()
    is_internal = models.BooleanField(default=False)
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name='work_notes')
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='work_notes', null=True, blank=True)
    change = models.ForeignKey('changes.Change', on_delete=models.CASCADE, related_name='work_notes', null=True, blank=True)
    problem = models.ForeignKey('problems.Problem', on_delete=models.CASCADE, related_name='work_notes', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_notes"
        ordering = ["-created_at"]


class Activity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    actor_ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activities')
    incident = models.ForeignKey('incidents.Incident', on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    change = models.ForeignKey('changes.Change', on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    problem = models.ForeignKey('problems.Problem', on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    config_item = models.ForeignKey(
        'assets.ConfigurationItem',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activities',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activities"
        ordering = ["-created_at"]


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size = models.BigIntegerField()
    path = models.CharField(max_length=500)
    
    incident = models.ForeignKey('incidents.Incident', on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    change = models.ForeignKey('changes.Change', on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    problem = models.ForeignKey('problems.Problem', on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='uploaded_attachments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attachments"
        ordering = ["-created_at"]


class IncidentProblem(models.Model):
    class LinkType(models.TextChoices):
        CAUSED_BY = "CAUSED_BY", "Caused By"
        RELATED = "RELATED", "Related"
        SYMPTOM_OF = "SYMPTOM_OF", "Symptom Of"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey('incidents.Incident', on_delete=models.CASCADE, related_name='linked_problems')
    problem = models.ForeignKey('problems.Problem', on_delete=models.CASCADE, related_name='linked_incidents')
    link_type = models.CharField(max_length=20, choices=LinkType.choices, default=LinkType.RELATED)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "incident_problems"


class IncidentChange(models.Model):
    class LinkType(models.TextChoices):
        RELATED_CHANGE = "RELATED_CHANGE", "Related Change"
        FIXED_BY_CHANGE = "FIXED_BY_CHANGE", "Fixed By Change"
        CAUSED_BY_CHANGE = "CAUSED_BY_CHANGE", "Caused By Change"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        'incidents.Incident',
        on_delete=models.CASCADE,
        related_name='linked_changes',
    )
    change = models.ForeignKey(
        'changes.Change',
        on_delete=models.CASCADE,
        related_name='linked_incidents',
    )
    link_type = models.CharField(max_length=30, choices=LinkType.choices, default=LinkType.RELATED_CHANGE)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "incident_changes"
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "change"],
                name="uniq_incident_change_link",
            )
        ]


class UnmatchedAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    alert_name = models.CharField(max_length=255)
    reason = models.CharField(max_length=255)

    class Meta:
        db_table = "unmatched_alerts"
        ordering = ["-received_at"]
