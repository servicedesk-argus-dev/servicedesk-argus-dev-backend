import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.mixins import OrgQuerysetMixin
from apps.common.pagination import DefaultPagination
from apps.common.permissions import DenyViewerMutations, can_manage_service_desk
from apps.common.responses import failure, success

from .models import CatalogCategory, CatalogItem, CatalogTask, RequestedItem, ServiceRequest
from .serializers import (
    CatalogCategorySerializer,
    CatalogItemSerializer,
    CatalogTaskSerializer,
    CatalogTaskUpdateSerializer,
    ensure_fulfillment_tasks,
    ServiceRequestCreateSerializer,
    ServiceRequestSerializer,
    ServiceRequestUpdateSerializer,
    sync_request_lifecycle,
)

logger = logging.getLogger(__name__)


def _is_catalog_manager(user):
    return can_manage_service_desk(user)


def _can_work_catalog_task(user, task):
    if _is_catalog_manager(user):
        return True
    if task.assigned_to_id == getattr(user, "id", None):
        return True
    if task.assignment_group_id:
        return task.assignment_group.members.filter(user=user).exists()
    return False


class CatalogCategoryListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    pagination_class = None
    queryset = CatalogCategory.objects.all()
    serializer_class = CatalogCategorySerializer

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("items").order_by("sort_order", "name")
        if self.request.method == "GET":
            qs = qs.filter(is_active=True)
        return qs

    def create(self, request, *args, **kwargs):
        if not _is_catalog_manager(request.user):
            return failure("Only admins, managers, or team leads can configure catalog categories.", status_code=403)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            category = serializer.save()
            return success(CatalogCategorySerializer(category).data, "Category created successfully.", 201)
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return success(CatalogCategorySerializer(qs, many=True).data)


class CatalogItemListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    pagination_class = DefaultPagination
    queryset = CatalogItem.objects.all()
    serializer_class = CatalogItemSerializer

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("category", "fulfillment_group", "organization")
            .order_by("name")
        )
        if self.request.method == "GET":
            qs = qs.filter(is_active=True, category__is_active=True)

        item_type = self.request.query_params.get("type")
        category_id = self.request.query_params.get("category") or self.request.query_params.get("categoryId")
        search = self.request.query_params.get("search", "").strip()

        if item_type:
            qs = qs.filter(type=item_type)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(short_description__icontains=search)
                | Q(description__icontains=search)
            )
        return qs

    def create(self, request, *args, **kwargs):
        if not _is_catalog_manager(request.user):
            return failure("Only admins, managers, or team leads can configure catalog items.", status_code=403)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            item = serializer.save()
            return success(CatalogItemSerializer(item).data, "Catalog item created successfully.", 201)
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = CatalogItemSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return success(CatalogItemSerializer(qs, many=True).data)


class CatalogItemDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    http_method_names = ["get", "patch", "head", "options"]
    queryset = CatalogItem.objects.all()
    serializer_class = CatalogItemSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("category", "fulfillment_group", "organization")
            .filter(category__is_active=True)
        )

    def retrieve(self, request, *args, **kwargs):
        return success(CatalogItemSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        if not _is_catalog_manager(request.user):
            return failure("Only admins, managers, or team leads can update catalog items.", status_code=403)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            item = serializer.save()
            return success(CatalogItemSerializer(item).data, "Catalog item updated successfully.")
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)


class ServiceRequestListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    pagination_class = DefaultPagination
    queryset = ServiceRequest.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ServiceRequestCreateSerializer
        return ServiceRequestSerializer

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related(
                "requested_for",
                "opened_by",
                "assigned_to",
                "assignment_group",
                "approved_by",
                "organization",
            )
            .prefetch_related("items__catalog_item", "items__tasks")
            .order_by("-created_at")
        )

        state = self.request.query_params.get("state")
        priority = self.request.query_params.get("priority")
        search = self.request.query_params.get("search", "").strip()

        if state:
            qs = qs.filter(state=state)
        if priority:
            qs = qs.filter(priority=priority)
        if search:
            qs = qs.filter(
                Q(number__icontains=search)
                | Q(short_description__icontains=search)
                | Q(description__icontains=search)
                | Q(requested_for__email__icontains=search)
            )
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ServiceRequestSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return success(ServiceRequestSerializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            service_request = serializer.save()
            return success(
                ServiceRequestSerializer(service_request).data,
                "Service request submitted successfully.",
                201,
            )
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)
        except Exception:
            logger.exception("Error creating service request")
            return failure("Failed to create service request.", status_code=400)


class MyServiceRequestListView(ServiceRequestListCreateView):
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().filter(Q(opened_by=self.request.user) | Q(requested_for=self.request.user))


class ServiceRequestDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    http_method_names = ["get", "patch", "head", "options"]
    queryset = ServiceRequest.objects.all()

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "requested_for",
                "opened_by",
                "assigned_to",
                "assignment_group",
                "approved_by",
                "organization",
            )
            .prefetch_related("items__catalog_item", "items__tasks")
        )

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ServiceRequestUpdateSerializer
        return ServiceRequestSerializer

    def retrieve(self, request, *args, **kwargs):
        return success(ServiceRequestSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        if not _is_catalog_manager(request.user):
            return failure("Only admins, managers, or team leads can update service requests.", status_code=403)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            service_request = serializer.save()
            sync_request_lifecycle(service_request)
            return success(ServiceRequestSerializer(service_request).data, "Service request updated successfully.")
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)


class ServiceRequestApproveView(OrgQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated]
    queryset = ServiceRequest.objects.all()

    def get_queryset(self):
        return (
            ServiceRequest.objects.select_related("organization")
            .prefetch_related("items")
            .all()
        )

    def post(self, request, pk):
        if not _is_catalog_manager(request.user):
            return failure("Only admins, managers, or team leads can approve service requests.", status_code=403)
        record = ServiceRequest.objects.filter(id=pk).first()
        if record is None:
            return failure("Service request not found.", status_code=404)
        if record.state not in {ServiceRequest.State.NEW, ServiceRequest.State.APPROVAL, ServiceRequest.State.APPROVED}:
            return failure("This request is not waiting for approval.", status_code=400)

        record.state = ServiceRequest.State.FULFILLMENT
        record.approved_by = request.user
        record.approved_at = timezone.now()
        record.save(update_fields=["state", "approved_by", "approved_at", "updated_at"])
        record.items.update(state=RequestedItem.State.IN_PROGRESS)
        ensure_fulfillment_tasks(record)
        record = (
            ServiceRequest.objects.select_related(
                "requested_for",
                "opened_by",
                "assigned_to",
                "assignment_group",
                "approved_by",
                "organization",
            )
            .prefetch_related("items__catalog_item", "items__tasks")
            .get(id=record.id)
        )
        return success(ServiceRequestSerializer(record).data, "Service request approved and moved to fulfillment.")


class ServiceRequestRejectView(OrgQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated]
    queryset = ServiceRequest.objects.all()

    def post(self, request, pk):
        if not _is_catalog_manager(request.user):
            return failure("Only admins, managers, or team leads can reject service requests.", status_code=403)
        record = ServiceRequest.objects.filter(id=pk).first()
        if record is None:
            return failure("Service request not found.", status_code=404)
        if record.state in {ServiceRequest.State.CLOSED, ServiceRequest.State.CANCELLED}:
            return failure("This request is already closed.", status_code=400)

        reason = request.data.get("reason") or request.data.get("cancelReason") or "Rejected"
        record.state = ServiceRequest.State.CANCELLED
        record.cancel_reason = reason
        record.save(update_fields=["state", "cancel_reason", "updated_at"])
        record.items.update(state=RequestedItem.State.CANCELLED)
        record = (
            ServiceRequest.objects.select_related(
                "requested_for",
                "opened_by",
                "assigned_to",
                "assignment_group",
                "approved_by",
                "organization",
            )
            .prefetch_related("items__catalog_item", "items__tasks")
            .get(id=record.id)
        )
        return success(ServiceRequestSerializer(record).data, "Service request rejected.")


class ServiceRequestCloseView(OrgQuerysetMixin, generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    queryset = ServiceRequest.objects.all()

    def post(self, request, pk):
        record = self.get_queryset().filter(id=pk).first()
        if record is None:
            return failure("Service request not found.", status_code=404)
        if not (_is_catalog_manager(request.user) or request.user.id in {record.opened_by_id, record.requested_for_id}):
            return failure("You do not have permission to close this service request.", status_code=403)
        if record.state not in {ServiceRequest.State.FULFILLED, ServiceRequest.State.FULFILLMENT}:
            return failure("Only fulfilled or in-progress service requests can be closed.", status_code=400)
        record.state = ServiceRequest.State.CLOSED
        record.closed_at = timezone.now()
        record.save(update_fields=["state", "closed_at", "updated_at"])
        record.items.exclude(state=RequestedItem.State.CANCELLED).update(state=RequestedItem.State.CLOSED)
        record = ServiceRequest.objects.select_related(
            "requested_for",
            "opened_by",
            "assigned_to",
            "assignment_group",
            "approved_by",
            "organization",
        ).prefetch_related("items__catalog_item", "items__tasks").get(id=record.id)
        return success(ServiceRequestSerializer(record).data, "Service request closed.")


class ServiceRequestReopenView(OrgQuerysetMixin, generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    queryset = ServiceRequest.objects.all()

    def post(self, request, pk):
        record = self.get_queryset().filter(id=pk).first()
        if record is None:
            return failure("Service request not found.", status_code=404)
        if not (_is_catalog_manager(request.user) or request.user.id in {record.opened_by_id, record.requested_for_id}):
            return failure("You do not have permission to reopen this service request.", status_code=403)
        if record.state not in {ServiceRequest.State.CLOSED, ServiceRequest.State.FULFILLED}:
            return failure("Only closed or fulfilled service requests can be reopened.", status_code=400)
        record.state = ServiceRequest.State.FULFILLMENT
        record.closed_at = None
        record.save(update_fields=["state", "closed_at", "updated_at"])
        record.items.filter(state__in=[RequestedItem.State.CLOSED, RequestedItem.State.FULFILLED]).update(
            state=RequestedItem.State.IN_PROGRESS
        )
        ensure_fulfillment_tasks(record)
        record = ServiceRequest.objects.select_related(
            "requested_for",
            "opened_by",
            "assigned_to",
            "assignment_group",
            "approved_by",
            "organization",
        ).prefetch_related("items__catalog_item", "items__tasks").get(id=record.id)
        return success(ServiceRequestSerializer(record).data, "Service request reopened.")


class CatalogTaskDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    http_method_names = ["get", "patch", "head", "options"]
    organization_lookup = "ritm__request__organization"
    queryset = CatalogTask.objects.all()

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "ritm",
                "ritm__request",
                "ritm__request__organization",
                "ritm__catalog_item",
                "assigned_to",
                "assignment_group",
            )
        )

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CatalogTaskUpdateSerializer
        return CatalogTaskSerializer

    def retrieve(self, request, *args, **kwargs):
        return success(CatalogTaskSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        if not _can_work_catalog_task(request.user, task):
            return failure("You can update only catalog tasks assigned to you or your team.", status_code=403)
        serializer = self.get_serializer(task, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            task = serializer.save()
            sync_request_lifecycle(task.ritm.request)
            task = self.get_queryset().get(id=task.id)
            return success(CatalogTaskSerializer(task).data, "Catalog task updated successfully.")
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)
