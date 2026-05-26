from django.utils import timezone
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from apps.common.activity_log import create_activity
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import (
    ChangeApprovalRBAC,
    ChangeTransitionRBAC,
    DenyViewerMutations,
    can_assign_service_record,
    can_edit_service_record,
    user_has_any_permission,
)
from apps.common.responses import failure, success
from .models import Change, Approval
from .serializers import ChangeSerializer, ChangeCreateSerializer, ChangeUpdateSerializer, ApprovalSerializer


CHANGE_ACTIVITY_FIELDS = {
    "short_description": "Short description",
    "description": "Description",
    "type": "Type",
    "state": "State",
    "risk_level": "Risk",
    "category": "Category",
    "assigned_to": "Assigned to",
    "assignment_group": "Assignment group",
    "justification": "Justification",
    "implementation_plan": "Implementation plan",
    "rollback_plan": "Backout plan",
    "test_plan": "Test plan",
    "communication_plan": "Communication plan",
    "planned_start_date": "Planned start",
    "planned_end_date": "Planned end",
    "actual_start_date": "Actual start",
    "actual_end_date": "Actual end",
    "affected_services": "Affected services",
    "downtime": "Downtime",
    "user_impact": "User impact",
    "review_notes": "Review notes",
    "closure_code": "Closure code",
}

ASSIGNMENT_FIELDS = {"assigned_to", "assignment_group"}


def _activity_value(value):
    if value is None:
        return ""
    if hasattr(value, "name"):
        return value.name
    if hasattr(value, "email"):
        return value.email
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class ChangeListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['state', 'type', 'risk_level', 'category']
    queryset = Change.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(number__icontains=search) | 
                Q(short_description__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset.select_related('assigned_to', 'created_by', 'assignment_group').prefetch_related('approvals', 'affected_cis__config_item', 'linked_incidents__incident')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ChangeCreateSerializer
        return ChangeSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        if not user_has_any_permission(request.user, "change:create", "change:manage"):
            return failure("You do not have permission to create changes.", status_code=403)
        if ASSIGNMENT_FIELDS.intersection(request.data.keys()) and not user_has_any_permission(
            request.user,
            "change:assign",
            "change:manage",
        ):
            return failure("Only NOC, leads, or admins can set change assignment.", status_code=403)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change = serializer.save()
        create_activity(
            request=request,
            action="CREATED",
            description=f"Created change {change.number}",
            user=request.user,
            change=change,
        )
        return success(ChangeSerializer(change, context=self.get_serializer_context()).data, "change created", 201)


class ChangeDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations, ChangeTransitionRBAC]
    queryset = Change.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ChangeUpdateSerializer
        return ChangeSerializer

    def get_queryset(self):
        return super().get_queryset().select_related('assigned_to', 'created_by', 'assignment_group').prefetch_related('approvals', 'affected_cis__config_item', 'linked_incidents__incident', 'work_notes__author', 'activities__user')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_edit_service_record(request.user, instance):
            return failure("Only assigned engineers, NOC, leads, or admins can edit this change.", status_code=403)
        if ASSIGNMENT_FIELDS.intersection(request.data.keys()) and not can_assign_service_record(request.user, instance):
            return failure("Only NOC, leads, or admins can change assignment.", status_code=403)
        tracked_before = {
            field: _activity_value(getattr(instance, field, None))
            for field in CHANGE_ACTIVITY_FIELDS
        }
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        change = serializer.save()

        lifecycle_updates = []
        if change.state == Change.State.IMPLEMENTING and change.actual_start_date is None:
            change.actual_start_date = timezone.now()
            lifecycle_updates.append("actual_start_date")
        if change.state in {Change.State.CLOSED, Change.State.CANCELLED} and change.actual_end_date is None:
            change.actual_end_date = timezone.now()
            lifecycle_updates.append("actual_end_date")
        if lifecycle_updates:
            change.save(update_fields=lifecycle_updates + ["updated_at"])

        for field, label in CHANGE_ACTIVITY_FIELDS.items():
            before = tracked_before[field]
            after = _activity_value(getattr(change, field, None))
            if before != after:
                create_activity(
                    request=request,
                    action="FIELD_CHANGED",
                    description=f"{label} changed",
                    old_value=before,
                    new_value=after,
                    user=request.user,
                    change=change,
                )

        change = self.get_queryset().filter(pk=change.pk).first()
        return success(ChangeSerializer(change, context=self.get_serializer_context()).data)


class ApprovalCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations, ChangeApprovalRBAC]
    serializer_class = ApprovalSerializer
    
    def perform_create(self, serializer):
        change_id = self.kwargs.get('change_id')
        serializer.save(approver=self.request.user, change_id=change_id)


class ChangeApprovalDecisionView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations, ChangeApprovalRBAC]

    def post(self, request, change_id):
        organization = getattr(request, "organization", None)
        if organization is None:
            return failure("organization access denied", status_code=403)

        change = Change.objects.filter(organization=organization, pk=change_id).first()
        if change is None:
            return failure("change not found", status_code=404)

        decision = (request.data.get("state") or request.data.get("decision") or "").upper()
        if decision not in {Approval.State.APPROVED, Approval.State.REJECTED}:
            return failure("state must be APPROVED or REJECTED", status_code=400)

        comments = request.data.get("comments")
        approval, _created = Approval.objects.update_or_create(
            change=change,
            approver=request.user,
            defaults={
                "state": decision,
                "comments": comments,
                "approved_at": timezone.now() if decision == Approval.State.APPROVED else None,
            },
        )

        previous_state = change.state
        state_changed = False

        if decision == Approval.State.REJECTED:
            # Any rejection cancels the change immediately
            if change.state not in {Change.State.CLOSED, Change.State.CANCELLED}:
                change.state = Change.State.CANCELLED
                change.save(update_fields=["state", "updated_at"])
                state_changed = True
        elif decision == Approval.State.APPROVED and change.state == Change.State.APPROVAL:
            # Check quorum: all required approvers must have approved
            required_approvers = change.required_approvers.all() if hasattr(change, 'required_approvers') else []
            if required_approvers:
                # Multi-approver mode: check all have approved
                approved_ids = set(
                    change.approvals.filter(state=Approval.State.APPROVED).values_list("approver_id", flat=True)
                )
                required_ids = set(required_approvers.values_list("id", flat=True))
                all_approved = required_ids.issubset(approved_ids)
            else:
                # No required approvers defined: any manager/admin approval is sufficient
                all_approved = True

            if all_approved:
                change.state = Change.State.SCHEDULED
                change.save(update_fields=["state", "updated_at"])
                state_changed = True

        create_activity(
            request=request,
            action=f"APPROVAL_{decision}",
            description=f"Change approval {decision.lower()} by {request.user.email}"
                        + (" — Change SCHEDULED" if state_changed and decision == Approval.State.APPROVED else "")
                        + (" — Change CANCELLED" if state_changed and decision == Approval.State.REJECTED else ""),
            old_value=previous_state,
            new_value=change.state,
            user=request.user,
            change=change,
        )

        change = (
            Change.objects.filter(pk=change.pk)
            .select_related('assigned_to', 'created_by', 'assignment_group')
            .prefetch_related('approvals', 'affected_cis__config_item', 'linked_incidents__incident', 'work_notes__author', 'activities__user')
            .first()
        )
        return success(ChangeSerializer(change).data, "approval decision recorded")

