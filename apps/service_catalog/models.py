import uuid
from django.db import models
from apps.organizations.models import Organization
from django.contrib.auth import get_user_model

User = get_user_model()

class CatalogCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='catalog_categories')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_categories"
        verbose_name_plural = "Catalog Categories"

class CatalogItem(models.Model):
    class Type(models.TextChoices):
        HARDWARE = "HARDWARE", "Hardware"
        SOFTWARE = "SOFTWARE", "Software"
        ACCESS = "ACCESS", "Access"
        GENERAL = "GENERAL", "General"
        SERVICE = "SERVICE", "Service"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    short_description = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.GENERAL)
    
    category = models.ForeignKey(CatalogCategory, on_delete=models.CASCADE, related_name='items')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='catalog_items')
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    recurring_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="USD")
    approval_required = models.BooleanField(default=False)
    fulfillment_group = models.ForeignKey(
        'teams.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='catalog_items',
    )
    estimated_days = models.PositiveIntegerField(null=True, blank=True)
    form_schema = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    picture = models.URLField(blank=True, null=True)
    
    # Workflow / Execution Plan link
    workflow = models.ForeignKey('workflows.Workflow', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_items"

class ServiceRequest(models.Model):
    """The 'REQ' record - high level wrapper for a shopping cart order."""
    class State(models.TextChoices):
        NEW = "NEW", "New"
        APPROVAL = "APPROVAL", "Approval"
        APPROVED = "APPROVED", "Approved"
        FULFILLMENT = "FULFILLMENT", "Work in Progress"
        FULFILLED = "FULFILLED", "Fulfilled"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    short_description = models.CharField(max_length=255, default="")
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=2, default="P3")
    
    requested_for = models.ForeignKey(User, on_delete=models.PROTECT, related_name='service_requests')
    opened_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='opened_service_requests')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_service_requests',
    )
    assignment_group = models.ForeignKey(
        'teams.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_requests',
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_service_requests',
    )
    
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEW)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='service_requests')
    
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    approved_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_requests"

class RequestedItem(models.Model):
    """The 'RITM' record - specific instance of a catalog item."""
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        IN_PROGRESS = "IN_PROGRESS", "Work in Progress"
        FULFILLED = "FULFILLED", "Fulfilled"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='items')
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT)
    
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    quantity = models.IntegerField(default=1)
    
    # Option data (dynamic variables)
    variables = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "requested_items"

class CatalogTask(models.Model):
    """The 'SCTASK' record - fulfillment tasks generated by workflow."""
    class State(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "Work in Progress"
        CLOSED_COMPLETE = "CLOSED_COMPLETE", "Closed Complete"
        CLOSED_INCOMPLETE = "CLOSED_INCOMPLETE", "Closed Incomplete"
        CLOSED_SKIPPED = "CLOSED_SKIPPED", "Closed Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, db_index=True)
    
    ritm = models.ForeignKey(RequestedItem, on_delete=models.CASCADE, related_name='tasks')
    
    short_description = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    state = models.CharField(max_length=20, choices=State.choices, default=State.OPEN)
    
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assignment_group = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_tasks"
