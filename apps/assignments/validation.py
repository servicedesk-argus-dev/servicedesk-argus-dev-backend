from django.db.models import Q
from rest_framework import serializers

from apps.common.permissions import is_service_desk_staff
from apps.teams.models import Team, TeamMember


def assignment_team_queryset_for(organization):
    queryset = Team.objects.filter(is_active=True)
    if organization is None:
        return queryset.filter(organization__isnull=True)
    return queryset.filter(Q(organization=organization) | Q(organization__isnull=True))


def validate_assignment_targets(*, assignment_group, assigned_to, organization):
    if assignment_group:
        allowed_team = assignment_team_queryset_for(organization).filter(id=assignment_group.id).exists()
        if not allowed_team:
            raise serializers.ValidationError(
                {"assignment_group": "Selected assignment group is not active for this client."}
            )

    if assigned_to:
        if not assigned_to.is_active or not assigned_to.is_active_member:
            raise serializers.ValidationError({"assigned_to": "Selected assignee is not active."})
        if not is_service_desk_staff(assigned_to):
            raise serializers.ValidationError({"assigned_to": "Selected assignee must be an internal resolver."})
        if organization and assigned_to.organization_id not in (None, organization.id):
            raise serializers.ValidationError(
                {"assigned_to": "Selected assignee is not available for this client."}
            )

    if assignment_group and assigned_to:
        is_member = TeamMember.objects.filter(
            team=assignment_group,
            user=assigned_to,
            user__is_active=True,
            user__is_active_member=True,
        ).exists()
        if not is_member:
            raise serializers.ValidationError(
                {"assigned_to": "Selected assignee must be a member of the assignment group."}
            )


def validate_assignment_attrs(attrs, *, organization, instance=None):
    if "assignment_group" not in attrs and "assigned_to" not in attrs:
        return attrs

    assignment_group = attrs.get("assignment_group", getattr(instance, "assignment_group", None))
    assigned_to = attrs.get("assigned_to", getattr(instance, "assigned_to", None))
    validate_assignment_targets(
        assignment_group=assignment_group,
        assigned_to=assigned_to,
        organization=organization,
    )
    return attrs
