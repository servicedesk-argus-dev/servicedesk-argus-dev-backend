from rest_framework import generics, serializers, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.utils import timezone
from apps.common.activity_log import create_activity
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import (
    DenyViewerMutations,
    IncidentTransitionRBAC,
    can_assign_service_record,
    can_edit_service_record,
    is_service_desk_staff,
    user_has_any_permission,
)
from apps.common.responses import success, failure
from apps.common.pagination import DefaultPagination
from apps.assignments.validation import validate_assignment_targets
from apps.changes.models import Change
from apps.problems.models import Problem
from apps.sla.services import refresh_incident_sla_state
from .models import Incident, WorkNote, Activity, Attachment, IncidentProblem, IncidentChange
from .serializers import IncidentSerializer, IncidentCreateSerializer, IncidentUpdateSerializer, WorkNoteSerializer


ACTIVITY_FIELD_LABELS = {
    "short_description": "Short description",
    "description": "Description",
    "state": "State",
    "impact": "Impact",
    "urgency": "Urgency",
    "priority": "Priority",
    "category": "Category",
    "subcategory": "Subcategory",
    "assigned_to": "Assigned to",
    "assignment_group": "Assignment group",
    "hold_reason": "Hold reason",
    "resolution_code": "Resolution code",
    "resolution_notes": "Resolution notes",
}

ASSIGNMENT_FIELDS = {"assigned_to", "assignment_group"}


def _activity_value(value):
    if value is None:
        return ""
    if hasattr(value, "number"):
        return value.number
    if hasattr(value, "name"):
        return value.name
    if hasattr(value, "email"):
        return value.email
    return str(value)


def _incident_queryset_for_request(request):
    queryset = Incident.objects.all()
    if is_service_desk_staff(request.user):
        org_id = (
            request.query_params.get("organization")
            or request.query_params.get("organization_id")
            or getattr(request, "organization_id", None)
        )
        if org_id:
            return queryset.filter(organization_id=org_id)
        return queryset
    organization = getattr(request, "organization", None) or getattr(request.user, "organization", None)
    return queryset.filter(organization=organization)


from .filters import IncidentFilter

class IncidentListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    filter_backends = [DjangoFilterBackend]
    filterset_class = IncidentFilter
    queryset = Incident.objects.all()
    pagination_class = DefaultPagination

    def get_queryset(self):
        queryset = _incident_queryset_for_request(self.request)
        return queryset.select_related('assigned_to', 'created_by', 'assignment_group').prefetch_related('work_notes', 'linked_problems__problem', 'linked_changes__change')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return IncidentCreateSerializer
        return IncidentSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        if not user_has_any_permission(request.user, "incident:create", "incident:manage"):
            return failure("You do not have permission to create incidents.", status_code=403)
        can_set_initial_assignment = is_service_desk_staff(request.user) and user_has_any_permission(
            request.user,
            "incident:create",
            "incident:manage",
        )
        if ASSIGNMENT_FIELDS.intersection(request.data.keys()) and not (
            can_set_initial_assignment
            or user_has_any_permission(request.user, "incident:assign", "incident:manage")
        ):
            return failure("Only NOC, leads, or admins can set incident assignment.", status_code=403)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = serializer.save()
        create_activity(
            request=request,
            action="CREATED",
            description=f"Created incident {incident.number}",
            user=request.user,
            incident=incident,
        )
        return success(IncidentSerializer(incident, context=self.get_serializer_context()).data, "incident created", 201)


class IncidentDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations, IncidentTransitionRBAC]
    queryset = Incident.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return IncidentUpdateSerializer
        return IncidentSerializer

    def get_queryset(self):
        return _incident_queryset_for_request(self.request).select_related('assigned_to', 'created_by', 'assignment_group').prefetch_related('work_notes', 'activities', 'attachments', 'linked_problems__problem', 'linked_changes__change')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_edit_service_record(request.user, instance):
            return failure("Only assigned engineers, NOC, leads, or admins can edit this incident.", status_code=403)
        if ASSIGNMENT_FIELDS.intersection(request.data.keys()) and not can_assign_service_record(request.user, instance):
            return failure("Only NOC, leads, or admins can change incident assignment.", status_code=403)
        previous_state = instance.state
        tracked_before = {
            field: _activity_value(getattr(instance, field, None))
            for field in ACTIVITY_FIELD_LABELS
        }
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        incident = serializer.save()

        lifecycle_fields = refresh_incident_sla_state(incident, previous_state=previous_state)
        if lifecycle_fields:
            incident.save(update_fields=list(set(lifecycle_fields + ["updated_at"])))

        for field, label in ACTIVITY_FIELD_LABELS.items():
            before = tracked_before[field]
            after = _activity_value(getattr(incident, field, None))
            if before != after:
                create_activity(
                    request=request,
                    action="FIELD_CHANGED",
                    description=f"{label} changed",
                    old_value=before,
                    new_value=after,
                    user=request.user,
                    incident=incident,
                )

        incident = self.get_queryset().filter(pk=incident.pk).first()
        return success(IncidentSerializer(incident, context=self.get_serializer_context()).data)


class IncidentStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        queryset = _incident_queryset_for_request(request)
        
        stats = {
            'total': queryset.count(),
            'open': queryset.filter(state__in=['NEW', 'IN_PROGRESS', 'ON_HOLD', 'ESCALATED']).count(),
            'p1': queryset.filter(priority='P1').count(),
            'p2': queryset.filter(priority='P2').count(),
            'p3': queryset.filter(priority='P3').count(),
            'p4': queryset.filter(priority='P4').count(),
            'resolved': queryset.filter(state='RESOLVED').count(),
            'closed': queryset.filter(state='CLOSED').count(),
            'sla_breached': queryset.filter(sla_breached=True).count(),
        }
        
        return success(stats)


class IncidentProblemLinkView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if incident is None:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can link incidents.", status_code=403)
        if is_service_desk_staff(request.user) and not user_has_any_permission(request.user, "incident:link", "incident:manage"):
            return failure("You do not have permission to link incidents to problems.", status_code=403)
        organization = incident.organization

        problem_id = request.data.get("problem_id") or request.data.get("problemId")
        if not problem_id:
            return failure("problem_id is required", status_code=400)

        problem = Problem.objects.filter(organization=organization, pk=problem_id).first()
        if problem is None:
            return failure("problem not found", status_code=404)

        link_type = request.data.get("link_type") or request.data.get("linkType") or IncidentProblem.LinkType.RELATED
        if link_type not in IncidentProblem.LinkType.values:
            return failure("invalid link type", status_code=400)

        notes = request.data.get("notes")
        link, created = IncidentProblem.objects.get_or_create(
            incident=incident,
            problem=problem,
            defaults={"link_type": link_type, "notes": notes},
        )
        if not created:
            changed = False
            if link.link_type != link_type:
                link.link_type = link_type
                changed = True
            if notes is not None and link.notes != notes:
                link.notes = notes
                changed = True
            if changed:
                link.save(update_fields=["link_type", "notes"])

        create_activity(
            request=request,
            action="PROBLEM_LINKED",
            description=f"Linked problem {problem.number}",
            user=request.user,
            incident=incident,
            problem=problem,
        )

        incident = (
            Incident.objects.filter(pk=incident.pk)
            .select_related('assigned_to', 'created_by', 'assignment_group')
            .prefetch_related('work_notes', 'activities', 'attachments', 'linked_problems__problem', 'linked_changes__change')
            .first()
        )
        return success(
            IncidentSerializer(incident, context={"request": request}).data,
            "problem linked to incident" if created else "incident problem link updated",
            201 if created else 200,
        )


class IncidentProblemUnlinkView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def delete(self, request, pk, link_id):
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if incident is None:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can unlink incidents.", status_code=403)
        if is_service_desk_staff(request.user) and not user_has_any_permission(request.user, "incident:link", "incident:manage"):
            return failure("You do not have permission to unlink incident problems.", status_code=403)

        link = IncidentProblem.objects.filter(pk=link_id, incident=incident).select_related("problem").first()
        if link is None:
            return failure("problem link not found", status_code=404)

        problem_number = link.problem.number
        problem = link.problem
        link.delete()
        create_activity(
            request=request,
            action="PROBLEM_UNLINKED",
            description=f"Unlinked problem {problem_number}",
            user=request.user,
            incident=incident,
            problem=problem,
        )
        return success({"id": str(link_id)}, "problem unlinked from incident")


class IncidentChangeLinkView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if incident is None:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can link incidents.", status_code=403)
        if is_service_desk_staff(request.user) and not user_has_any_permission(request.user, "incident:link", "incident:manage"):
            return failure("You do not have permission to link incidents to changes.", status_code=403)
        organization = incident.organization

        change_id = request.data.get("change_id") or request.data.get("changeId")
        if not change_id:
            return failure("change_id is required", status_code=400)

        change = Change.objects.filter(organization=organization, pk=change_id).first()
        if change is None:
            return failure("change not found", status_code=404)

        link_type = request.data.get("link_type") or request.data.get("linkType") or IncidentChange.LinkType.RELATED_CHANGE
        if link_type not in IncidentChange.LinkType.values:
            return failure("invalid link type", status_code=400)

        notes = request.data.get("notes")
        link, created = IncidentChange.objects.get_or_create(
            incident=incident,
            change=change,
            defaults={"link_type": link_type, "notes": notes},
        )
        if not created:
            changed = False
            if link.link_type != link_type:
                link.link_type = link_type
                changed = True
            if notes is not None and link.notes != notes:
                link.notes = notes
                changed = True
            if changed:
                link.save(update_fields=["link_type", "notes"])

        create_activity(
            request=request,
            action="CHANGE_LINKED",
            description=f"Linked change {change.number}",
            user=request.user,
            incident=incident,
            change=change,
        )

        incident = (
            Incident.objects.filter(pk=incident.pk)
            .select_related('assigned_to', 'created_by', 'assignment_group')
            .prefetch_related('work_notes', 'activities', 'attachments', 'linked_problems__problem', 'linked_changes__change')
            .first()
        )
        return success(
            IncidentSerializer(incident, context={"request": request}).data,
            "change linked to incident" if created else "incident change link updated",
            201 if created else 200,
        )


class IncidentChangeUnlinkView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def delete(self, request, pk, link_id):
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if incident is None:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can unlink incidents.", status_code=403)
        if is_service_desk_staff(request.user) and not user_has_any_permission(request.user, "incident:link", "incident:manage"):
            return failure("You do not have permission to unlink incident changes.", status_code=403)

        link = IncidentChange.objects.filter(pk=link_id, incident=incident).select_related("change").first()
        if link is None:
            return failure("change link not found", status_code=404)

        change_number = link.change.number
        change = link.change
        link.delete()
        create_activity(
            request=request,
            action="CHANGE_UNLINKED",
            description=f"Unlinked change {change_number}",
            user=request.user,
            incident=incident,
            change=change,
        )
        return success({"id": str(link_id)}, "change unlinked from incident")


class WorkNoteCreateView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, incident_id):
        incident = _incident_queryset_for_request(request).filter(pk=incident_id).first()
        if incident is None:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can add work notes.", status_code=403)

        data = request.data.copy()
        if not is_service_desk_staff(request.user):
            data["is_internal"] = False
        serializer = WorkNoteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(author=request.user, incident=incident)
        create_activity(
            request=request,
            action="WORK_NOTE_ADDED",
            description="Work note added",
            user=request.user,
            incident=incident,
        )
        return success(WorkNoteSerializer(note).data, "work note added", 201)

class IncidentTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        incident = (
            _incident_queryset_for_request(request).filter(pk=pk)
            .select_related('assigned_to', 'created_by', 'assignment_group')
            .prefetch_related('activities__user', 'work_notes__author')
            .first()
        )
        if incident is None:
            return failure("incident not found", status_code=404)

        items = []

        for activity in incident.activities.all():
            items.append(
                {
                    "id": str(activity.id),
                    "type": "activity",
                    "action": activity.action,
                    "description": activity.description,
                    "oldValue": activity.old_value,
                    "newValue": activity.new_value,
                    "actorIp": activity.actor_ip,
                    "userAgent": activity.user_agent or None,
                    "createdAt": activity.created_at.isoformat() if activity.created_at else None,
                    "user": (
                        {
                            "id": str(activity.user.id),
                            "firstName": activity.user.first_name,
                            "lastName": activity.user.last_name,
                            "email": activity.user.email,
                        }
                        if activity.user_id
                        else None
                    ),
                }
            )

        for note in incident.work_notes.all():
            items.append(
                {
                    "id": str(note.id),
                    "type": "work_note",
                    "action": "NOTE_ADDED",
                    "description": note.content,
                    "isInternal": note.is_internal,
                    "source": note.source,
                    "createdAt": note.created_at.isoformat() if note.created_at else None,
                    "user": (
                        {
                            "id": str(note.author.id),
                            "firstName": note.author.first_name,
                            "lastName": note.author.last_name,
                            "email": note.author.email,
                        }
                        if note.author_id
                        else None
                    ),
                }
            )

        items.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
        return success(items)


class IncidentLiveContextView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        incident = (
            _incident_queryset_for_request(request).filter(pk=pk)
            .select_related("config_item")
            .first()
        )
        if incident is None:
            return failure("incident not found", status_code=404)

        config_item = incident.config_item
        hostname = getattr(config_item, "hostname", None) or getattr(config_item, "name", None)
        ip_address = getattr(config_item, "ip_address", None)
        os_name = (getattr(config_item, "os", None) or "").strip()
        os_type = "windows" if "windows" in os_name.lower() else "linux" if os_name else None

        past_incidents = []
        if config_item is not None:
            related = (
                _incident_queryset_for_request(request)
                .filter(
                    config_item=config_item,
                )
                .exclude(pk=incident.pk)
                .order_by("-created_at")[:5]
            )
            past_incidents = [
                {
                    "id": str(item.id),
                    "number": item.number,
                    "priority": item.priority,
                    "state": item.state,
                    "shortDescription": item.short_description,
                    "createdAt": item.created_at.isoformat() if item.created_at else None,
                }
                for item in related
            ]

        payload = {
            "alertContext": {
                "alertName": incident.source_alert_name or incident.short_description,
                "instance": hostname or ip_address,
                "hostname": hostname,
                "ip": ip_address,
                "source": incident.source,
            },
            "metrics": {
                "available": False,
                "error": None,
                "osType": os_type,
                "cpu": {"usagePct": 0, "cores": None},
                "memory": {"usedPct": 0, "totalBytes": None},
                "load": {"m1": 0, "m5": 0, "cores": 1},
                "filesystems": [],
                "interfaces": [],
                "sysInfo": {
                    "hostname": hostname,
                    "os": os_name or None,
                    "kernel": None,
                    "arch": None,
                    "uptimeSeconds": None,
                },
            },
            "firingAlerts": [],
            "pastIncidents": past_incidents,
        }
        return success(payload)


class IncidentEscalateView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        if not is_service_desk_staff(request.user):
            return failure("Only service desk staff can escalate incidents.", status_code=403)
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can escalate this incident.", status_code=403)
        if not user_has_any_permission(request.user, "incident:escalate", "incident:manage"):
            return failure("You do not have permission to escalate incidents.", status_code=403)

        if incident.state in {Incident.State.RESOLVED, Incident.State.CLOSED, Incident.State.CANCELLED}:
            return failure("Cannot escalate a resolved, closed, or cancelled incident.", status_code=400)

        reason = request.data.get("reason", "Manual escalation")
        previous_priority = incident.priority
        incident.state = Incident.State.ESCALATED
        incident.escalation_level = getattr(incident, 'escalation_level', 0) + 1
        # Bump priority if not already P1
        priority_ladder = [Incident.Priority.P4, Incident.Priority.P3, Incident.Priority.P2, Incident.Priority.P1]
        current_idx = priority_ladder.index(incident.priority) if incident.priority in priority_ladder else 2
        incident.priority = priority_ladder[min(current_idx + 1, 3)]
        incident.save()

        create_activity(
            request=request,
            action="ESCALATED",
            description=f"Escalated (Level {incident.escalation_level}): {reason}",
            old_value=previous_priority,
            new_value=incident.priority,
            user=request.user,
            incident=incident
        )

        return success(IncidentSerializer(incident, context={"request": request}).data, "incident escalated")


class IncidentReassignView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        if not is_service_desk_staff(request.user):
            return failure("Only service desk staff can assign incidents.", status_code=403)
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if not can_assign_service_record(request.user, incident):
            return failure("Only NOC, leads, or admins can assign incidents.", status_code=403)
            
        from apps.accounts.models import User
        from apps.teams.models import Team

        assigned_to = incident.assigned_to
        assignment_group = incident.assignment_group

        if "assigned_to" in request.data:
            assigned_to_id = request.data.get("assigned_to")
            if assigned_to_id:
                assigned_to = User.objects.filter(pk=assigned_to_id).first()
                if assigned_to is None:
                    return failure("Selected assignee was not found.", status_code=400)
            else:
                assigned_to = None

        if "assignment_group" in request.data:
            assignment_group_id = request.data.get("assignment_group")
            if assignment_group_id:
                assignment_group = Team.objects.filter(pk=assignment_group_id).first()
                if assignment_group is None:
                    return failure("Selected assignment group was not found.", status_code=400)
            else:
                assignment_group = None

        try:
            validate_assignment_targets(
                assignment_group=assignment_group,
                assigned_to=assigned_to,
                organization=incident.organization,
            )
        except serializers.ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)

        incident.assigned_to = assigned_to
        incident.assignment_group = assignment_group
                
        incident.save()
        
        create_activity(
            request=request,
            action="REASSIGNED",
            description=f"Reassigned to {incident.assigned_to.email if incident.assigned_to else 'None'}",
            user=request.user,
            incident=incident
        )
        
        return success(IncidentSerializer(incident, context={"request": request}).data, "incident reassigned")


class IncidentResolveView(APIView):
    """Marks incident as RESOLVED (Engineer action). Sets resolved_at."""
    permission_classes = [IsAuthenticated, DenyViewerMutations, IncidentTransitionRBAC]

    def post(self, request, pk):
        from django.utils import timezone
        if not is_service_desk_staff(request.user):
            return failure("Only service desk staff can resolve incidents.", status_code=403)
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can resolve this incident.", status_code=403)
        if not user_has_any_permission(request.user, "incident:resolve", "incident:manage"):
            return failure("You do not have permission to resolve incidents.", status_code=403)

        if incident.state in {Incident.State.RESOLVED, Incident.State.CLOSED, Incident.State.CANCELLED}:
            return failure(f"Incident is already {incident.state}.", status_code=400)

        resolution_code = request.data.get("resolution_code")
        resolution_notes = request.data.get("resolution_notes")

        if not resolution_code:
            return failure("resolution_code is required to resolve an incident.", status_code=400)
        if not resolution_notes:
            return failure("resolution_notes are required to resolve an incident.", status_code=400)
        if resolution_code not in Incident.ResolutionCode.values:
            return failure(f"Invalid resolution_code. Valid: {Incident.ResolutionCode.values}", status_code=400)

        incident.state = Incident.State.RESOLVED
        incident.resolution_code = resolution_code
        incident.resolution_notes = resolution_notes
        incident.resolved_at = timezone.now()
        incident.save()

        create_activity(
            request=request,
            action="RESOLVED",
            description=f"Incident resolved with code: {resolution_code}",
            old_value=Incident.State.IN_PROGRESS,
            new_value=Incident.State.RESOLVED,
            user=request.user,
            incident=incident
        )

        incident = Incident.objects.select_related(
            'assigned_to', 'created_by', 'assignment_group'
        ).prefetch_related('work_notes', 'activities', 'attachments').get(pk=incident.pk)
        return success(IncidentSerializer(incident, context={"request": request}).data, "incident resolved")


class IncidentCloseView(APIView):
    """Permanently closes a RESOLVED incident. Requires manager/admin."""
    permission_classes = [IsAuthenticated, DenyViewerMutations, IncidentTransitionRBAC]

    def post(self, request, pk):
        from django.utils import timezone
        if not is_service_desk_staff(request.user):
            return failure("Only service desk staff can close incidents.", status_code=403)
        if not user_has_any_permission(request.user, "incident:close", "incident:manage"):
            return failure("Only NOC, leads, or admins can close incidents.", status_code=403)
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)

        if incident.state != Incident.State.RESOLVED:
            return failure("Only RESOLVED incidents can be closed. Resolve it first.", status_code=400)

        incident.state = Incident.State.CLOSED
        incident.closed_at = timezone.now()
        incident.save()

        create_activity(
            request=request,
            action="CLOSED",
            description="Incident permanently closed.",
            user=request.user,
            incident=incident
        )

        return success(IncidentSerializer(incident, context={"request": request}).data, "incident closed")


class IncidentReopenView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        from django.utils import timezone
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can reopen this incident.", status_code=403)
        if is_service_desk_staff(request.user) and not user_has_any_permission(request.user, "incident:reopen", "incident:manage"):
            return failure("You do not have permission to reopen incidents.", status_code=403)

        if incident.state not in [Incident.State.RESOLVED, Incident.State.CLOSED]:
            return failure("Only RESOLVED or CLOSED incidents can be reopened.", status_code=400)

        reason = request.data.get("reason", "Reopened by user")
        previous_state = incident.state
        incident.state = Incident.State.IN_PROGRESS
        incident.resolved_at = None
        incident.closed_at = None
        incident.save()

        create_activity(
            request=request,
            action="REOPENED",
            description=f"Reopened from {previous_state}: {reason}",
            old_value=previous_state,
            new_value=Incident.State.IN_PROGRESS,
            user=request.user,
            incident=incident
        )

        return success(IncidentSerializer(incident, context={"request": request}).data, "incident reopened")


class IncidentBulkUpdateView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request):
        ids = request.data.get("ids", [])
        updates = request.data.get("updates", {})
        
        if not ids:
            return failure("no incident ids provided", status_code=400)
        if not user_has_any_permission(request.user, "incident:bulk_update", "incident:manage"):
            return failure("Only NOC, leads, or admins can bulk update incidents.", status_code=403)
            
        incidents = _incident_queryset_for_request(request).filter(pk__in=ids)
        count = incidents.count()
        
        # Simple implementation - iterate and save to trigger signals/logic
        for incident in incidents:
            if "state" in updates:
                incident.state = updates["state"]
            if "priority" in updates:
                incident.priority = updates["priority"]
            if "assigned_to" in updates:
                from apps.accounts.models import User
                user = User.objects.filter(pk=updates["assigned_to"]).first()
                if user:
                    incident.assigned_to = user
            incident.save()
            
            create_activity(
                request=request,
                action="BULK_UPDATE",
                description=f"Bulk updated: {list(updates.keys())}",
                user=request.user,
                incident=incident
            )


class IncidentChildBulkOperationsView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        """Perform bulk operations on child incidents"""
        parent_incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if parent_incident is None:
            return failure("Parent incident not found", status_code=404)

        action = request.data.get("action")
        child_ids = request.data.get("child_ids", [])
        updates = request.data.get("updates", {})
        if not can_edit_service_record(request.user, parent_incident):
            return failure("Only assigned engineers, NOC, leads, or admins can update child incidents.", status_code=403)
        if ASSIGNMENT_FIELDS.intersection(updates.keys()) and not can_assign_service_record(request.user, parent_incident):
            return failure("Only NOC, leads, or admins can change incident assignment.", status_code=403)
        if action == "resolve" and not user_has_any_permission(request.user, "incident:resolve", "incident:manage"):
            return failure("You do not have permission to resolve child incidents.", status_code=403)
        if action == "close" and not user_has_any_permission(request.user, "incident:close", "incident:manage"):
            return failure("You do not have permission to close child incidents.", status_code=403)

        # If no specific child IDs provided, operate on all children
        if not child_ids:
            children = parent_incident.child_incidents.all()
        else:
            children = parent_incident.child_incidents.filter(pk__in=child_ids)

        if not children.exists():
            return failure("No child incidents found", status_code=400)

        results = []
        
        for child in children:
            try:
                if action == "resolve":
                    if child.state not in [Incident.State.RESOLVED, Incident.State.CLOSED]:
                        child.state = Incident.State.RESOLVED
                        child.resolution_code = updates.get("resolution_code", "BULK_RESOLVED")
                        child.resolution_notes = updates.get("resolution_notes", f"Bulk resolved with parent {parent_incident.number}")
                        child.resolved_at = timezone.now()
                        child.save()
                        
                elif action == "close":
                    if child.state == Incident.State.RESOLVED:
                        child.state = Incident.State.CLOSED
                        child.closed_at = timezone.now()
                        child.save()
                        
                elif action == "update":
                    if "state" in updates:
                        child.state = updates["state"]
                    if "priority" in updates:
                        child.priority = updates["priority"]
                    if "assigned_to" in updates:
                        from apps.accounts.models import User
                        user = User.objects.filter(pk=updates["assigned_to"]).first()
                        if user:
                            child.assigned_to = user
                    child.save()

                create_activity(
                    request=request,
                    action=f"BULK_{action.upper()}",
                    description=f"Bulk {action} from parent {parent_incident.number}",
                    user=request.user,
                    incident=child
                )
                
                results.append({"id": child.id, "number": child.number, "status": "success"})
                
            except Exception as e:
                results.append({"id": child.id, "number": child.number, "status": "error", "error": str(e)})

        return success({
            "message": f"Bulk operation completed on {len(results)} child incidents",
            "results": results,
            "parent_id": parent_incident.id
        })
            
        return success({"updated_count": count}, f"successfully updated {count} incidents")


class IncidentExportCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import csv
        from django.http import HttpResponse
        from .filters import IncidentFilter
        
        queryset = _incident_queryset_for_request(request)
        filtered_qs = IncidentFilter(request.GET, queryset=queryset).qs
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="incidents_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Number', 'Short Description', 'Priority', 'State', 'Assigned To', 'Created At'])
        
        for incident in filtered_qs:
            writer.writerow([
                incident.number,
                incident.short_description,
                incident.priority,
                incident.state,
                incident.assigned_to.email if incident.assigned_to else 'Unassigned',
                incident.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])
            
        return response


class IncidentAttachmentUploadView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if is_service_desk_staff(request.user) and not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can upload attachments.", status_code=403)
            
        file_obj = request.FILES.get("file")
        if not file_obj:
            return failure("no file provided", status_code=400)
            
        # Basic validation
        if file_obj.size > 10 * 1024 * 1024: # 10MB limit
            return failure("file size exceeds 10MB limit", status_code=400)
            
        # Save file (simple local storage)
        import os
        from django.conf import settings
        from django.core.files.storage import default_storage
        
        path = default_storage.save(
            f"attachments/incidents/{incident.id}/{file_obj.name}",
            file_obj
        )
        
        attachment = Attachment.objects.create(
            incident=incident,
            filename=file_obj.name,
            original_name=file_obj.name,
            mime_type=file_obj.content_type,
            size=file_obj.size,
            path=path,
            uploaded_by=request.user
        )
        
        create_activity(
            request=request,
            action="ATTACHMENT_ADDED",
            description=f"Attachment added: {file_obj.name}",
            user=request.user,
            incident=incident
        )
        
        from .serializers import AttachmentSerializer
        return success(AttachmentSerializer(attachment).data, "attachment uploaded", 201)


class IncidentPromoteToProblemView(APIView):
    """
    POST /api/v1/incidents/<id>/promote-to-problem/
    Creates a Problem from this incident's context and auto-links them.
    RBAC: Engineer and above only.
    """
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        from apps.problems.models import Problem
        from apps.problems.serializers import ProblemSerializer
        from apps.common.utils import generate_record_number

        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can promote this incident.", status_code=403)

        if not user_has_any_permission(request.user, "incident:promote", "problem:create", "problem:manage"):
            return failure("Only Engineers and above can promote incidents to problems.", status_code=403)

        # Generate unique PRB number
        number = generate_record_number("PRB", incident.organization, "last_problem_number")

        problem = Problem.objects.create(
            number=number,
            short_description=incident.short_description,
            description=incident.description or "",
            priority=incident.priority,
            category=incident.category or "",
            organization=incident.organization,
            created_by=request.user,
            assigned_to=incident.assigned_to,
            assignment_group=incident.assignment_group,
        )

        # Link incident → problem
        IncidentProblem.objects.create(
            incident=incident,
            problem=problem,
            link_type=IncidentProblem.LinkType.CAUSED_BY,
            notes=f"Promoted from incident {incident.number}",
        )

        create_activity(
            request=request,
            action="PROMOTED_TO_PROBLEM",
            description=f"Promoted to Problem {problem.number}",
            user=request.user,
            incident=incident,
            problem=problem,
        )

        return success(ProblemSerializer(problem, context={"request": request}).data, f"Incident promoted to Problem {problem.number}", 201)


class IncidentPromoteToChangeView(APIView):
    """
    POST /api/v1/incidents/<id>/promote-to-change/
    Creates a Change from this incident's context and auto-links them.
    """
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        from apps.changes.serializers import ChangeSerializer
        from apps.common.utils import generate_record_number

        incident = _incident_queryset_for_request(request).filter(pk=pk).first()
        if not incident:
            return failure("incident not found", status_code=404)
        if not can_edit_service_record(request.user, incident):
            return failure("Only assigned engineers, NOC, leads, or admins can create a change from this incident.", status_code=403)

        if not user_has_any_permission(request.user, "incident:promote", "change:create", "change:manage"):
            return failure("Only Engineers and above can create changes from incidents.", status_code=403)

        link_type = request.data.get("link_type") or request.data.get("linkType") or IncidentChange.LinkType.FIXED_BY_CHANGE
        if link_type not in IncidentChange.LinkType.values:
            return failure("invalid link type", status_code=400)

        priority_to_risk = {
            Incident.Priority.P1: Change.RiskLevel.HIGH,
            Incident.Priority.P2: Change.RiskLevel.HIGH,
            Incident.Priority.P3: Change.RiskLevel.MEDIUM,
            Incident.Priority.P4: Change.RiskLevel.LOW,
        }
        change_type = request.data.get("change_type") or request.data.get("changeType") or Change.Type.NORMAL
        if change_type not in Change.Type.values:
            return failure("invalid change type", status_code=400)

        number = generate_record_number("CHG", incident.organization, "last_change_number")
        change = Change.objects.create(
            number=number,
            short_description=incident.short_description,
            description=incident.description or "",
            type=change_type,
            risk_level=priority_to_risk.get(incident.priority, Change.RiskLevel.MEDIUM),
            category=incident.category or "",
            organization=incident.organization,
            created_by=request.user,
            assigned_to=incident.assigned_to,
            assignment_group=incident.assignment_group,
            justification=f"Created from incident {incident.number}.",
            implementation_plan="Assess incident impact, prepare remediation steps, and implement during an approved window.",
            rollback_plan="Restore the previous known-good configuration if validation fails.",
            test_plan="Confirm the affected service is reachable and the original incident symptom is resolved.",
        )

        IncidentChange.objects.create(
            incident=incident,
            change=change,
            link_type=link_type,
            notes=f"Created from incident {incident.number}",
        )

        create_activity(
            request=request,
            action="PROMOTED_TO_CHANGE",
            description=f"Created change {change.number} from incident",
            user=request.user,
            incident=incident,
            change=change,
        )
        create_activity(
            request=request,
            action="CREATED_FROM_INCIDENT",
            description=f"Created from incident {incident.number}",
            user=request.user,
            incident=incident,
            change=change,
        )

        return success(ChangeSerializer(change, context={"request": request}).data, f"Incident linked to Change {change.number}", 201)
