import uuid
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    last_incident_number = models.PositiveIntegerField(default=0)
    last_change_number = models.PositiveIntegerField(default=0)
    last_problem_number = models.PositiveIntegerField(default=0)
    last_service_request_number = models.PositiveIntegerField(default=0)
    last_requested_item_number = models.PositiveIntegerField(default=0)
    last_catalog_task_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations"
        ordering = ["name"]

    def __str__(self):
        return self.name

