from decimal import Decimal
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.common.permissions import is_service_desk_staff
from apps.common.utils import generate_record_number
from apps.organizations.models import Organization
from apps.teams.models import Team

from .models import CatalogCategory, CatalogItem, CatalogTask, RequestedItem, ServiceRequest

User = get_user_model()


def team_summary(team):
    if not team:
        return None
    return {"id": str(team.id), "name": team.name}


def _first_int(value):
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


CATALOG_TASK_TERMINAL_STATES = {
    CatalogTask.State.CLOSED_COMPLETE,
    CatalogTask.State.CLOSED_INCOMPLETE,
    CatalogTask.State.CLOSED_SKIPPED,
}


def create_fulfillment_task(requested_item):
    """Create the ServiceNow-style SCTASK for a RITM only when fulfillment starts."""
    existing = requested_item.tasks.order_by("created_at").first()
    if existing:
        return existing

    catalog_item = requested_item.catalog_item
    request = requested_item.request
    return CatalogTask.objects.create(
        number=generate_record_number("SCTASK", request.organization, "last_catalog_task_number"),
        ritm=requested_item,
        short_description=f"Fulfill {catalog_item.name}",
        description=request.description or requested_item.notes or catalog_item.description,
        assignment_group=catalog_item.fulfillment_group or request.assignment_group,
        assigned_to=request.assigned_to,
    )


def ensure_fulfillment_tasks(service_request):
    for requested_item in service_request.items.select_related("catalog_item", "request").all():
        create_fulfillment_task(requested_item)


def sync_request_lifecycle(service_request):
    """Roll SCTASK states up to RITM and REQ, matching the ServiceNow request hierarchy."""
    changed_items = []
    for item in service_request.items.prefetch_related("tasks").all():
        tasks = list(item.tasks.all())
        next_state = item.state
        if tasks:
            if all(task.state == CatalogTask.State.CLOSED_COMPLETE for task in tasks):
                next_state = RequestedItem.State.FULFILLED
            elif all(task.state in CATALOG_TASK_TERMINAL_STATES for task in tasks):
                next_state = RequestedItem.State.CANCELLED
            elif any(task.state == CatalogTask.State.IN_PROGRESS for task in tasks):
                next_state = RequestedItem.State.IN_PROGRESS
            elif service_request.state == ServiceRequest.State.FULFILLMENT:
                next_state = RequestedItem.State.IN_PROGRESS

        if next_state != item.state:
            item.state = next_state
            item.updated_at = timezone.now()
            changed_items.append(item)

    if changed_items:
        RequestedItem.objects.bulk_update(changed_items, ["state", "updated_at"])

    items = list(RequestedItem.objects.filter(request=service_request))
    next_request_state = service_request.state
    update_fields = []
    if items and all(item.state == RequestedItem.State.FULFILLED for item in items):
        next_request_state = ServiceRequest.State.FULFILLED
        if not service_request.fulfilled_at:
            service_request.fulfilled_at = timezone.now()
            update_fields.append("fulfilled_at")
    elif items and all(item.state in {RequestedItem.State.FULFILLED, RequestedItem.State.CANCELLED, RequestedItem.State.CLOSED} for item in items):
        next_request_state = ServiceRequest.State.CANCELLED
    elif any(item.state == RequestedItem.State.IN_PROGRESS for item in items):
        next_request_state = ServiceRequest.State.FULFILLMENT

    if next_request_state != service_request.state:
        service_request.state = next_request_state
        update_fields.append("state")

    if update_fields:
        update_fields.append("updated_at")
        service_request.save(update_fields=update_fields)


def _active_organization_for_request(request):
    org_id = (
        request.data.get("organizationId")
        or request.data.get("organization_id")
        or request.query_params.get("organization")
        or request.query_params.get("organization_id")
        or getattr(request, "organization_id", None)
    )
    if org_id and is_service_desk_staff(request.user):
        return Organization.objects.filter(id=org_id, is_active=True).first()
    organization = getattr(request, "organization", None)
    if organization:
        return organization
    organization = getattr(request.user, "organization", None)
    if organization:
        return organization
    if is_service_desk_staff(request.user):
        return Organization.objects.filter(is_active=True).order_by("name").first()
    return None


def _has_explicit_organization_context(request):
    return bool(
        request.data.get("organizationId")
        or request.data.get("organization_id")
        or request.query_params.get("organization")
        or request.query_params.get("organization_id")
        or getattr(request, "organization_id", None)
    )


class CatalogCategoryMiniSerializer(serializers.ModelSerializer):
    sortOrder = serializers.IntegerField(source="sort_order", read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CatalogCategory
        fields = [
            "id",
            "name",
            "description",
            "icon",
            "sortOrder",
            "isActive",
            "createdAt",
            "updatedAt",
        ]


class CatalogItemMiniSerializer(serializers.ModelSerializer):
    shortDescription = serializers.CharField(source="short_description", read_only=True)
    categoryId = serializers.UUIDField(source="category_id", read_only=True)
    approvalRequired = serializers.BooleanField(source="approval_required", read_only=True)
    fulfillmentGroupId = serializers.UUIDField(source="fulfillment_group_id", read_only=True, allow_null=True)
    estimatedDays = serializers.IntegerField(source="estimated_days", read_only=True, allow_null=True)
    formSchema = serializers.JSONField(source="form_schema", read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    icon = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CatalogItem
        fields = [
            "id",
            "name",
            "shortDescription",
            "description",
            "categoryId",
            "type",
            "icon",
            "price",
            "currency",
            "approvalRequired",
            "fulfillmentGroupId",
            "estimatedDays",
            "formSchema",
            "isActive",
            "createdAt",
            "updatedAt",
        ]

    def get_icon(self, obj):
        return obj.picture


class CatalogCategorySerializer(serializers.ModelSerializer):
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    catalogItems = serializers.SerializerMethodField()
    _count = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CatalogCategory
        fields = [
            "id",
            "name",
            "description",
            "icon",
            "sortOrder",
            "isActive",
            "catalogItems",
            "_count",
            "createdAt",
            "updatedAt",
        ]

    def get_catalogItems(self, obj):
        items = obj.items.filter(is_active=True).order_by("name")[:8]
        return CatalogItemMiniSerializer(items, many=True).data

    def get__count(self, obj):
        return {"catalogItems": obj.items.filter(is_active=True).count()}

    def create(self, validated_data):
        request = self.context["request"]
        organization = _active_organization_for_request(request)
        if organization is None:
            raise serializers.ValidationError("Organization context is required.")
        validated_data["organization"] = organization
        return super().create(validated_data)


class CatalogItemSerializer(serializers.ModelSerializer):
    shortDescription = serializers.CharField(source="short_description")
    categoryId = serializers.PrimaryKeyRelatedField(
        source="category", queryset=CatalogCategory.objects.all()
    )
    approvalRequired = serializers.BooleanField(source="approval_required", required=False)
    fulfillmentGroupId = serializers.PrimaryKeyRelatedField(
        source="fulfillment_group",
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
    )
    estimatedDays = serializers.IntegerField(source="estimated_days", required=False, allow_null=True)
    formSchema = serializers.JSONField(source="form_schema", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    icon = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        coerce_to_string=False,
    )
    category = CatalogCategoryMiniSerializer(read_only=True)
    fulfillmentGroup = serializers.SerializerMethodField()
    _count = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CatalogItem
        fields = [
            "id",
            "name",
            "shortDescription",
            "description",
            "categoryId",
            "type",
            "icon",
            "price",
            "currency",
            "approvalRequired",
            "fulfillmentGroupId",
            "estimatedDays",
            "formSchema",
            "isActive",
            "category",
            "fulfillmentGroup",
            "_count",
            "createdAt",
            "updatedAt",
        ]

    def get_icon(self, obj):
        return obj.picture

    def get_fulfillmentGroup(self, obj):
        return team_summary(obj.fulfillment_group)

    def get__count(self, obj):
        return {"requestItems": obj.requesteditem_set.count()}

    def validate(self, attrs):
        request = self.context["request"]
        organization = _active_organization_for_request(request)
        category = attrs.get("category") or getattr(self.instance, "category", None)
        fulfillment_group = attrs.get("fulfillment_group") or getattr(self.instance, "fulfillment_group", None)

        if organization is None:
            raise serializers.ValidationError("Organization context is required.")
        if category and category.organization_id != organization.id:
            raise serializers.ValidationError({"categoryId": "Selected category is outside this organization."})
        if fulfillment_group and fulfillment_group.organization_id not in (None, organization.id):
            raise serializers.ValidationError(
                {"fulfillmentGroupId": "Selected team is outside this organization."}
            )
        attrs["organization"] = organization
        return attrs

    def create(self, validated_data):
        if validated_data.get("price") is None:
            validated_data["price"] = Decimal("0.00")
        if not validated_data.get("description"):
            validated_data["description"] = validated_data["short_description"]
        return super().create(validated_data)


class CatalogTaskSerializer(serializers.ModelSerializer):
    shortDescription = serializers.CharField(source="short_description", read_only=True)
    requestedItemId = serializers.UUIDField(source="ritm_id", read_only=True)
    assignedTo = UserSerializer(source="assigned_to", read_only=True)
    assignedToId = serializers.UUIDField(source="assigned_to_id", read_only=True, allow_null=True)
    assignmentGroup = serializers.SerializerMethodField()
    assignmentGroupId = serializers.UUIDField(source="assignment_group_id", read_only=True, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CatalogTask
        fields = [
            "id",
            "number",
            "requestedItemId",
            "state",
            "shortDescription",
            "short_description",
            "description",
            "assignedToId",
            "assignedTo",
            "assignmentGroupId",
            "assignmentGroup",
            "createdAt",
            "updatedAt",
        ]

    def get_assignmentGroup(self, obj):
        return team_summary(obj.assignment_group)


class CatalogTaskUpdateSerializer(serializers.ModelSerializer):
    shortDescription = serializers.CharField(source="short_description", required=False, allow_blank=True)
    assignedToId = serializers.PrimaryKeyRelatedField(
        source="assigned_to",
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    assignmentGroupId = serializers.PrimaryKeyRelatedField(
        source="assignment_group",
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = CatalogTask
        fields = [
            "state",
            "shortDescription",
            "description",
            "assignedToId",
            "assignmentGroupId",
        ]

    def validate(self, attrs):
        organization = self.instance.ritm.request.organization
        assigned_to = attrs.get("assigned_to")
        assignment_group = attrs.get("assignment_group")

        if assigned_to and assigned_to.organization_id not in (None, organization.id):
            raise serializers.ValidationError({"assignedToId": "Selected assignee is outside this organization."})
        if assignment_group and assignment_group.organization_id not in (None, organization.id):
            raise serializers.ValidationError(
                {"assignmentGroupId": "Selected team is outside this organization."}
            )
        return attrs


class RequestedItemSerializer(serializers.ModelSerializer):
    serviceRequestId = serializers.UUIDField(source="request_id", read_only=True)
    catalogItemId = serializers.UUIDField(source="catalog_item_id", read_only=True)
    formData = serializers.JSONField(source="variables", read_only=True)
    catalogItem = CatalogItemMiniSerializer(source="catalog_item", read_only=True)
    tasks = CatalogTaskSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = RequestedItem
        fields = [
            "id",
            "number",
            "serviceRequestId",
            "catalogItemId",
            "state",
            "quantity",
            "formData",
            "variables",
            "notes",
            "catalogItem",
            "tasks",
            "createdAt",
            "updatedAt",
        ]


class ServiceRequestSerializer(serializers.ModelSerializer):
    shortDescription = serializers.CharField(source="short_description", read_only=True)
    catalogItemName = serializers.CharField(source="catalog_item_label", read_only=True, allow_null=True)
    category = serializers.CharField(source="category_label", read_only=True, allow_null=True)
    estimatedDelivery = serializers.CharField(source="estimated_delivery", read_only=True, allow_null=True)
    requestedById = serializers.UUIDField(source="requested_for_id", read_only=True)
    openedById = serializers.UUIDField(source="opened_by_id", read_only=True)
    assignedToId = serializers.UUIDField(source="assigned_to_id", read_only=True, allow_null=True)
    assignmentGroupId = serializers.UUIDField(source="assignment_group_id", read_only=True, allow_null=True)
    approvedById = serializers.UUIDField(source="approved_by_id", read_only=True, allow_null=True)
    approvedAt = serializers.DateTimeField(source="approved_at", read_only=True, allow_null=True)
    fulfilledAt = serializers.DateTimeField(source="fulfilled_at", read_only=True, allow_null=True)
    closedAt = serializers.DateTimeField(source="closed_at", read_only=True, allow_null=True)
    cancelReason = serializers.CharField(source="cancel_reason", read_only=True, allow_null=True)
    requestedBy = UserSerializer(source="requested_for", read_only=True)
    openedBy = UserSerializer(source="opened_by", read_only=True)
    assignedTo = UserSerializer(source="assigned_to", read_only=True)
    assignmentGroup = serializers.SerializerMethodField()
    approvedBy = UserSerializer(source="approved_by", read_only=True)
    requestItems = RequestedItemSerializer(source="items", many=True, read_only=True)
    activities = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            "id",
            "number",
            "shortDescription",
            "description",
            "state",
            "priority",
            "catalogItemName",
            "category",
            "estimatedDelivery",
            "requestedById",
            "openedById",
            "assignedToId",
            "assignmentGroupId",
            "approvedById",
            "approvedAt",
            "fulfilledAt",
            "closedAt",
            "cancelReason",
            "requestedBy",
            "openedBy",
            "assignedTo",
            "assignmentGroup",
            "approvedBy",
            "requestItems",
            "activities",
            "createdAt",
            "updatedAt",
        ]

    def get_assignmentGroup(self, obj):
        return team_summary(obj.assignment_group)

    def get_activities(self, obj):
        activities = [
            {
                "id": f"{obj.id}:created",
                "action": "created",
                "description": f"Request {obj.number} was submitted.",
                "createdAt": obj.created_at,
                "user": UserSerializer(obj.opened_by).data if obj.opened_by_id else None,
            }
        ]
        if obj.approved_at:
            activities.append(
                {
                    "id": f"{obj.id}:approved",
                    "action": "approved",
                    "description": "Request approved and moved to fulfillment.",
                    "createdAt": obj.approved_at,
                    "user": UserSerializer(obj.approved_by).data if obj.approved_by_id else None,
                }
            )
        for item in obj.items.all():
            for task in item.tasks.all():
                activities.append(
                    {
                        "id": str(task.id),
                        "action": "catalog_task",
                        "description": f"{task.number} is {task.get_state_display()}.",
                        "createdAt": task.updated_at,
                        "user": UserSerializer(task.assigned_to).data if task.assigned_to_id else None,
                    }
                )
        if obj.fulfilled_at:
            activities.append(
                {
                    "id": f"{obj.id}:fulfilled",
                    "action": "fulfilled",
                    "description": f"Request {obj.number} was fulfilled.",
                    "createdAt": obj.fulfilled_at,
                    "user": None,
                }
            )
        return sorted(activities, key=lambda row: row.get("createdAt") or obj.created_at, reverse=True)


class ServiceRequestCreateSerializer(serializers.Serializer):
    catalogItemId = serializers.UUIDField(required=False, allow_null=True)
    catalogItemName = serializers.CharField(required=False, allow_blank=True, max_length=200)
    category = serializers.CharField(required=False, allow_blank=True, max_length=100)
    estimatedDelivery = serializers.CharField(required=False, allow_blank=True, max_length=100)
    quantity = serializers.IntegerField(default=1, min_value=1, max_value=99)
    priority = serializers.ChoiceField(choices=["P1", "P2", "P3", "P4"], default="P3")
    shortDescription = serializers.CharField(required=False, allow_blank=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    variables = serializers.JSONField(required=False)
    formData = serializers.JSONField(required=False)
    requestedForId = serializers.UUIDField(required=False)
    organizationId = serializers.UUIDField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        catalog_item = None
        catalog_item_id = attrs.get("catalogItemId")

        if catalog_item_id:
            catalog_item = (
                CatalogItem.objects.select_related("category", "fulfillment_group", "organization")
                .filter(id=catalog_item_id, is_active=True)
                .first()
            )
            if catalog_item is None:
                raise serializers.ValidationError({"catalogItemId": "Catalog item not found."})

        organization = _active_organization_for_request(request)
        if catalog_item and is_service_desk_staff(request.user) and not _has_explicit_organization_context(request):
            organization = catalog_item.organization

        if organization is None:
            raise serializers.ValidationError("Organization context is required.")
        if catalog_item and catalog_item.organization_id != organization.id:
            raise serializers.ValidationError({"catalogItemId": "Catalog item is outside this organization."})

        catalog_item_name = (attrs.get("catalogItemName") or "").strip()
        category_label = (attrs.get("category") or "").strip()
        estimated_delivery = (attrs.get("estimatedDelivery") or "").strip()

        if catalog_item is None:
            if not catalog_item_name:
                raise serializers.ValidationError({"catalogItemName": "Catalog item is required."})
            category_name = category_label or "General"
            category_label = category_name
            category = CatalogCategory.objects.filter(
                organization=organization,
                name__iexact=category_name,
            ).order_by("created_at").first()
            if category is None:
                category = CatalogCategory.objects.create(
                    organization=organization,
                    name=category_name,
                    description="Typed service request category",
                    is_active=True,
                )

            catalog_item = CatalogItem.objects.filter(
                organization=organization,
                category=category,
                name__iexact=catalog_item_name,
            ).order_by("created_at").first()
            if catalog_item is None:
                catalog_item = CatalogItem.objects.create(
                    organization=organization,
                    category=category,
                    name=catalog_item_name,
                    short_description=catalog_item_name,
                    description=attrs.get("description") or attrs.get("notes") or catalog_item_name,
                    type=CatalogItem.Type.SERVICE,
                    estimated_days=_first_int(estimated_delivery),
                    is_active=True,
                )
        else:
            catalog_item_name = catalog_item_name or catalog_item.name
            category_label = category_label or getattr(catalog_item.category, "name", "") or catalog_item.get_type_display()
            if not estimated_delivery and catalog_item.estimated_days:
                estimated_delivery = f"{catalog_item.estimated_days} day(s)"

        requested_for = request.user
        requested_for_id = attrs.get("requestedForId")
        if requested_for_id:
            if not is_service_desk_staff(request.user):
                raise serializers.ValidationError({"requestedForId": "Clients can only request for themselves."})
            requested_for = User.objects.filter(id=requested_for_id, organization=organization, is_active=True).first()
            if requested_for is None:
                raise serializers.ValidationError({"requestedForId": "Requested-for user not found."})

        attrs["organization"] = organization
        attrs["catalog_item"] = catalog_item
        attrs["catalog_item_label"] = catalog_item_name
        attrs["category_label"] = category_label
        attrs["estimated_delivery"] = estimated_delivery
        attrs["requested_for"] = requested_for
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        organization = validated_data["organization"]
        catalog_item = validated_data["catalog_item"]
        requested_for = validated_data["requested_for"]
        catalog_item_label = validated_data.get("catalog_item_label") or catalog_item.name
        category_label = validated_data.get("category_label") or getattr(catalog_item.category, "name", "")
        estimated_delivery = validated_data.get("estimated_delivery") or (
            f"{catalog_item.estimated_days} day(s)" if catalog_item.estimated_days else ""
        )
        quantity = validated_data.get("quantity", 1)
        needs_approval = catalog_item.approval_required
        variables = dict(validated_data.get("variables") or validated_data.get("formData") or {})
        variables.setdefault("catalog_item", catalog_item_label)
        if category_label:
            variables.setdefault("category", category_label)
        if estimated_delivery:
            variables.setdefault("estimated_delivery", estimated_delivery)
        description = validated_data.get("description") or validated_data.get("notes") or ""
        short_description = validated_data.get("shortDescription") or catalog_item_label

        service_request = ServiceRequest.objects.create(
            number=generate_record_number("REQ", organization, "last_service_request_number"),
            short_description=short_description,
            description=description,
            priority=validated_data.get("priority", "P3"),
            catalog_item_label=catalog_item_label,
            category_label=category_label,
            estimated_delivery=estimated_delivery,
            requested_for=requested_for,
            opened_by=request.user,
            organization=organization,
            assignment_group=catalog_item.fulfillment_group,
            state=ServiceRequest.State.APPROVAL if needs_approval else ServiceRequest.State.FULFILLMENT,
            total_price=(catalog_item.price or Decimal("0.00")) * quantity,
        )

        requested_item = RequestedItem.objects.create(
            number=generate_record_number("RITM", organization, "last_requested_item_number"),
            request=service_request,
            catalog_item=catalog_item,
            state=RequestedItem.State.PENDING if needs_approval else RequestedItem.State.IN_PROGRESS,
            quantity=quantity,
            variables=variables,
            notes=validated_data.get("notes") or "",
        )

        if not needs_approval:
            create_fulfillment_task(requested_item)
        return service_request


class ServiceRequestUpdateSerializer(serializers.ModelSerializer):
    shortDescription = serializers.CharField(source="short_description", required=False, allow_blank=True)
    assignedToId = serializers.PrimaryKeyRelatedField(
        source="assigned_to",
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    assignmentGroupId = serializers.PrimaryKeyRelatedField(
        source="assignment_group",
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
    )
    cancelReason = serializers.CharField(source="cancel_reason", required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ServiceRequest
        fields = [
            "shortDescription",
            "description",
            "state",
            "priority",
            "assignedToId",
            "assignmentGroupId",
            "cancelReason",
        ]

    def validate(self, attrs):
        organization = self.instance.organization
        assigned_to = attrs.get("assigned_to")
        assignment_group = attrs.get("assignment_group")

        if assigned_to and assigned_to.organization_id not in (None, organization.id):
            raise serializers.ValidationError({"assignedToId": "Selected assignee is outside this organization."})
        if assignment_group and assignment_group.organization_id not in (None, organization.id):
            raise serializers.ValidationError(
                {"assignmentGroupId": "Selected team is outside this organization."}
            )
        return attrs
