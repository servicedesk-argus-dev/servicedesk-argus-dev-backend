import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class LearningTrack(models.Model):
    class AudienceRole(models.TextChoices):
        NOC = "NOC", "NOC"
        INFRA = "INFRA", "Infra"
        DEVOPS = "DEVOPS", "DevOps"
        SOFTWARE = "SOFTWARE", "Software"
        SERVICE_DESK = "SERVICE_DESK", "Service Desk"
        GENERAL = "GENERAL", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    audience_role = models.CharField(max_length=40, choices=AudienceRole.choices, default=AudienceRole.GENERAL)
    description = models.TextField(blank=True)
    team = models.ForeignKey("teams.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="learning_tracks")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_learning_tracks",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_learning_tracks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_tracks"
        ordering = ["title"]

    def __str__(self):
        return self.title


class LearningModule(models.Model):
    class ModuleType(models.TextChoices):
        ARTICLE = "ARTICLE", "Article"
        SOP = "SOP", "SOP"
        VIDEO = "VIDEO", "Video"
        TASK = "TASK", "Task"
        LINK = "LINK", "Link"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey(LearningTrack, on_delete=models.CASCADE, related_name="modules")
    order = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    module_type = models.CharField(max_length=20, choices=ModuleType.choices, default=ModuleType.ARTICLE)
    content = models.TextField(blank=True)
    external_url = models.URLField(blank=True)
    estimated_minutes = models.PositiveIntegerField(default=30)
    is_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_modules"
        ordering = ["track", "order", "title"]
        unique_together = ["track", "order"]

    def __str__(self):
        return f"{self.track.title} - {self.title}"


class LearningEnrollment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey(LearningTrack, on_delete=models.CASCADE, related_name="enrollments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_enrollments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_learning_enrollments",
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentored_learning_enrollments",
    )
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_enrollments"
        ordering = ["-created_at"]
        unique_together = ["track", "user"]

    @property
    def is_overdue(self):
        return bool(self.due_date and self.status != self.Status.COMPLETED and self.due_date < timezone.now())

    def refresh_status(self):
        required_modules = self.track.modules.filter(is_required=True)
        total_required = required_modules.count()
        total_modules = self.track.modules.count()
        total_to_complete = total_required or total_modules
        completed_required = self.progress.filter(module__is_required=True, completed_at__isnull=False).count()
        completed_any = self.progress.filter(completed_at__isnull=False).count()
        completed_to_count = completed_required if total_required else completed_any

        if total_to_complete and completed_to_count >= total_to_complete:
            self.status = self.Status.COMPLETED
            self.completed_at = self.completed_at or timezone.now()
        elif completed_to_count:
            self.status = self.Status.IN_PROGRESS
            self.completed_at = None
        else:
            self.status = self.Status.ASSIGNED
            self.completed_at = None
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def __str__(self):
        return f"{self.user} - {self.track}"


class LearningProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(LearningEnrollment, on_delete=models.CASCADE, related_name="progress")
    module = models.ForeignKey(LearningModule, on_delete=models.CASCADE, related_name="progress")
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_learning_modules",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_progress"
        ordering = ["module__order"]
        unique_together = ["enrollment", "module"]

    @property
    def is_completed(self):
        return self.completed_at is not None
