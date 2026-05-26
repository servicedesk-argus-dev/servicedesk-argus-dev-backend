from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import DenyViewerMutations, IsAdminOrManager, is_service_desk_staff
from apps.common.responses import failure, success


from .models import Team, TeamMember
from .serializers import (
    TeamCreateSerializer, TeamMemberSerializer, TeamSerializer, TeamUpdateSerializer
)


class TeamListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']
    pagination_class = None
    queryset = Team.objects.all()
    
    def get_queryset(self):
        queryset = Team.objects.all()
        if is_service_desk_staff(self.request.user):
            org_id = (
                self.request.query_params.get("organization")
                or self.request.query_params.get("organization_id")
                or getattr(self.request, "organization_id", None)
            )
            if org_id:
                queryset = queryset.filter(Q(organization_id=org_id) | Q(organization__isnull=True))
            else:
                queryset = queryset.filter(organization__isnull=True)
        else:
            organization = getattr(self.request, "organization", None) or getattr(self.request.user, "organization", None)
            if organization is None:
                raise PermissionDenied("Organization access denied")
            queryset = queryset.filter(organization=organization)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        queryset = queryset.annotate(
            assignedIncidents=Count('assigned_incidents', distinct=True),
            assignedChanges=Count('assigned_changes', distinct=True),
            assignedProblems=Count('assigned_problems', distinct=True)
        )
        return queryset.select_related('manager').prefetch_related('members__user')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TeamCreateSerializer
        return TeamSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "message": "teams retrieved",
                "data": serializer.data,
                "pagination": {
                    "total": len(serializer.data),
                    "pages": 1,
                    "current": 1,
                    "next": None,
                    "previous": None,
                },
            },
            status=200,
        )
    
    def create(self, request, *args, **kwargs):
        if not IsAdminOrManager().has_permission(request, self):
            return failure("Only admins, NOC, and team leads can create teams", status_code=403)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = serializer.save()
        return success(TeamSerializer(team).data, "team created", 201)


class TeamDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    queryset = Team.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TeamUpdateSerializer
        return TeamSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related('manager').prefetch_related('members__user')
        return queryset.annotate(
            assignedIncidents=Count('assigned_incidents', distinct=True),
            assignedChanges=Count('assigned_changes', distinct=True),
            assignedProblems=Count('assigned_problems', distinct=True)
        )

    def partial_update(self, request, *args, **kwargs):
        if not IsAdminOrManager().has_permission(request, self):
            return failure("Only admins, NOC, and team leads can update teams", status_code=403)
        return super().partial_update(request, *args, **kwargs)


class TeamMemberCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    serializer_class = TeamMemberSerializer
    
    def perform_create(self, serializer):
        team_id = self.kwargs.get('team_id')
        team = Team.objects.filter(pk=team_id).first()
        if team is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("team not found")
        if not is_service_desk_staff(self.request.user) and team.organization_id != self.request.organization_id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("team access denied")
        serializer.save(team_id=team_id)


def _member_payload(member):
    user = member.user
    first_name = getattr(user, "first_name", "") or getattr(user, "firstName", "")
    last_name = getattr(user, "last_name", "") or getattr(user, "lastName", "")
    return {
        "id": str(member.id),
        "user": {
            "id": str(user.id),
            "firstName": first_name,
            "lastName": last_name,
            "email": user.email,
            "role": user.role_names[0] if user.role_names else "",
        },
        "team": {"id": str(member.team_id), "name": member.team.name},
        "isPrimary": member.role == "LEAD",
    }


class OnCallOverviewView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        teams = Team.objects.filter(organization=request.organization, is_active=True).prefetch_related("members__user")
        schedules = []
        covered = 0
        for team in teams:
            members = list(team.members.all())
            if members:
                members.sort(key=lambda m: m.joined_at)
                primary_member = members[0]
                covered += 1
                schedules.append(_member_payload(primary_member))

        return success(
            {
                "schedules": schedules,
                "stats": {
                    "activeSchedules": len(schedules),
                    "onCallNow": len(schedules),
                    "escalations": 0,
                    "teamsCovered": covered,
                },
            }
        )


class TeamOnCallView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def get(self, request, team_id):
        team = Team.objects.filter(id=team_id, organization=request.organization).first()
        if not team:
            return success({"schedules": []})
        members = team.members.select_related("user").order_by("joined_at")
        return success({"schedules": [_member_payload(member) for member in members]})

    def post(self, request, team_id):
        if not IsAdminOrManager().has_permission(request, self):
            return success({}, "Only admins and managers can manage on-call", 403)
        return success(
            {
                "teamId": team_id,
                "userId": request.data.get("userId"),
                "startTime": request.data.get("startTime"),
                "endTime": request.data.get("endTime"),
                "isPrimary": bool(request.data.get("isPrimary", True)),
                "createdAt": timezone.now().isoformat(),
            },
            "on-call schedule created",
            201,
        )


class TeamOnCallHistoryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        team = Team.objects.filter(id=team_id, organization=request.organization).first()
        if not team:
            return success({"entries": []})
        members = team.members.select_related("user").order_by("-joined_at")
        entries = [
            {
                "id": str(member.id),
                "user": _member_payload(member)["user"],
                "role": member.role,
                "joinedAt": member.joined_at.isoformat(),
            }
            for member in members
        ]
        return success(
            {"entries": entries},
            status_code=200,
        )


class TeamEscalationView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        team = Team.objects.filter(id=team_id, organization=request.organization).first()
        if not team:
            return success({"levels": []})
        members = list(team.members.select_related("user").order_by("joined_at"))
        levels = []
        for idx, member in enumerate(members[:3], start=1):
            payload = _member_payload(member)["user"]
            levels.append(
                {
                    "level": idx,
                    "name": f"L{idx}",
                    "user": payload,
                    "delayMinutes": 15 * idx,
                }
            )
        return success({"teamId": str(team.id), "levels": levels})
