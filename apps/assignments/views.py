from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from uuid import UUID
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import is_service_desk_staff
from apps.common.responses import success, failure
from apps.teams.models import Team, TeamMember
from apps.teams.serializers import TeamSerializer, TeamMemberSerializer
from apps.accounts.serializers import UserSerializer
from .models import AssignmentRule, CategoryGroupMapping, UserSkill, SkillRequirement
from .serializers import (
    AssignmentRuleSerializer, CategoryGroupMappingSerializer, 
    UserSkillSerializer, SkillRequirementSerializer
)
from .services import resolve_assignment


class AssignmentRuleListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    queryset = AssignmentRule.objects.all()
    serializer_class = AssignmentRuleSerializer


class AssignmentRuleDetailView(OrgQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = AssignmentRule.objects.all()
    serializer_class = AssignmentRuleSerializer


class CategoryGroupMappingListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    queryset = CategoryGroupMapping.objects.all()
    serializer_class = CategoryGroupMappingSerializer


class CategoryGroupMappingDetailView(OrgQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = CategoryGroupMapping.objects.all()
    serializer_class = CategoryGroupMappingSerializer


class UserSkillListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    queryset = UserSkill.objects.all()
    serializer_class = UserSkillSerializer


class SkillRequirementListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    queryset = SkillRequirement.objects.all()
    serializer_class = SkillRequirementSerializer


class AssignmentPreviewView(APIView):
    """
    Dry-run view to see what the assignment engine would suggest.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.incidents.models import Incident

        organization = getattr(request, "organization", None) or getattr(request.user, "organization", None)
        if organization is None:
            return failure("Organization access denied", status_code=403)

        config_item_id = request.data.get("config_item_id") or None
        if config_item_id is not None:
            try:
                config_item_id = str(UUID(str(config_item_id)))
            except (AttributeError, TypeError, ValueError):
                return failure("config_item_id must be a valid UUID", status_code=400)
        
        # Build a temporary incident object (not saved)
        temp_incident = Incident(
            organization=organization,
            category=request.data.get("category"),
            subcategory=request.data.get("subcategory"),
            impact=request.data.get("impact", "TEAM"),
            urgency=request.data.get("urgency", "MEDIUM"),
            config_item_id=config_item_id
        )
        
        group, individual = resolve_assignment(temp_incident)
        
        return success({
            "suggested_group": {
                "id": str(group.id),
                "name": group.name
            } if group else None,
            "suggested_user": {
                "id": str(individual.id),
                "name": f"{individual.first_name} {individual.last_name}".strip() or individual.email
            } if individual else None,
            "reason": "Engine computed suggestion"
        })


class TeamMembersFilteredView(APIView):
    """
    Returns only members of a specific team.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        organization = getattr(request, "organization", None) or getattr(request.user, "organization", None)
        team_scope = Q(team__organization__isnull=True)
        if organization is not None:
            team_scope |= Q(team__organization=organization)
        if is_service_desk_staff(request.user):
            org_id = request.query_params.get("organization") or request.query_params.get("organization_id")
            if org_id:
                team_scope = Q(team__organization_id=org_id) | Q(team__organization__isnull=True)
            else:
                team_scope = Q()

        members = TeamMember.objects.filter(
            team_scope,
            team_id=team_id,
            team__is_active=True,
        ).select_related('user')
        
        users = [m.user for m in members if m.user.is_active]
        return success(UserSerializer(users, many=True).data)
