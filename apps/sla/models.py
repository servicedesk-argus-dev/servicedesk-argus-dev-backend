import uuid
from datetime import time, timedelta
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class SLADefinition(models.Model):
    class AppliesTo(models.TextChoices):
        INCIDENT = "INCIDENT", "Incident"
        CHANGE = "CHANGE", "Change"
        PROBLEM = "PROBLEM", "Problem"

    class Priority(models.TextChoices):
        P1 = "P1", "P1 - Critical"
        P2 = "P2", "P2 - High"
        P3 = "P3", "P3 - Moderate"
        P4 = "P4", "P4 - Low"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="sla_definitions",
    )
    name = models.CharField(max_length=160)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices, default=AppliesTo.INCIDENT)
    priority = models.CharField(max_length=2, choices=Priority.choices)
    response_time_minutes = models.PositiveIntegerField(default=60)
    resolution_time_minutes = models.PositiveIntegerField(default=1440)
    business_hours_only = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    start_condition = models.JSONField(default=dict, help_text="JSON conditions to start the SLA.")
    pause_condition = models.JSONField(default=dict, blank=True, help_text="JSON conditions to pause the SLA.")
    stop_condition = models.JSONField(default=dict, help_text="JSON conditions to stop the SLA.")
    reset_condition = models.JSONField(default=dict, blank=True, help_text="JSON conditions to reset the SLA.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sla_definitions"
        ordering = ["applies_to", "priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "applies_to", "priority"],
                name="uniq_sla_definition_org_applies_priority",
            )
        ]

    def __str__(self):
        return f"{self.organization} {self.applies_to} {self.priority}"


class BusinessCalendar(models.Model):
    """Per-organization working week and daily window (used when SLA is business-hours only)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="business_calendar",
    )
    timezone_name = models.CharField(max_length=64, default="UTC")
    workday_start = models.TimeField(default=time(9, 0))
    workday_end = models.TimeField(default=time(17, 0))
    work_weekdays = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sla_business_calendars"


class SLAHoliday(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="sla_holidays",
    )
    date = models.DateField()
    name = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "sla_holidays"
        constraints = [
            models.UniqueConstraint(fields=["organization", "date"], name="uniq_sla_holiday_org_date"),
        ]

class TaskSLA(models.Model):
    class Stage(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PAUSED = "PAUSED", "Paused"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Generic relation to Incident, Problem, or Change
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    sla_definition = models.ForeignKey(
        SLADefinition,
        on_delete=models.CASCADE,
        related_name="task_slas",
    )
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.IN_PROGRESS)
    
    start_time = models.DateTimeField(default=timezone.now)
    pause_time = models.DateTimeField(blank=True, null=True)
    stop_time = models.DateTimeField(blank=True, null=True)
    
    # Track the exact amount of time spent paused
    total_pause_duration = models.DurationField(default=timedelta(0))
    
    business_elapsed_time = models.DurationField(default=timedelta(0))
    percentage_elapsed = models.FloatField(default=0.0)
    has_breached = models.BooleanField(default=False)
    notified_thresholds = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task_slas"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.sla_definition.name} for {self.content_object} - {self.stage}"
