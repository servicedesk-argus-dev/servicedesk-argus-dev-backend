from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Team, TeamMember
from apps.accounts.serializers import UserSerializer
from apps.common.permissions import is_service_desk_staff
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer

User = get_user_model()


class TeamMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        source='user',
        queryset=User.objects.all(),
        write_only=True,
        required=False,
    )
    team_id = serializers.UUIDField(source='team.id', read_only=True)
    joinedAt = serializers.DateTimeField(source='joined_at', read_only=True)

    class Meta:
        model = TeamMember
        fields = ['id', 'user', 'user_id', 'team_id', 'role', 'joined_at', 'joinedAt']
        read_only_fields = ['id', 'joined_at']

    def validate_user_id(self, user):
        if not user.is_active or not user.is_active_member:
            raise serializers.ValidationError("Selected user is not active.")
        if not is_service_desk_staff(user):
            raise serializers.ValidationError("Team members must be internal resolver users.")
        return user


class TeamSerializer(serializers.ModelSerializer):
    manager = UserSerializer(read_only=True)
    manager_id = serializers.PrimaryKeyRelatedField(
        source='manager',
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source='organization',
        queryset=Organization.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    members = serializers.SerializerMethodField()
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    slackChannel = serializers.CharField(source='slack_channel', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    _count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Team
        fields = [
            'id', 'name', 'description', 'email', 'slack_channel', 'slackChannel',
            'manager', 'manager_id', 'is_active', 'isActive', 'organization',
            'organization_id', 'members', 'member_ids', 'created_at', 'createdAt',
            'updated_at', 'updatedAt', '_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get__count(self, obj):
        return {
            "assignedIncidents": getattr(obj, "assignedIncidents", 0),
            "assignedChanges": getattr(obj, "assignedChanges", 0),
            "assignedProblems": getattr(obj, "assignedProblems", 0),
        }

    def get_members(self, obj):
        members = obj.members.select_related("user").filter(user__is_active=True, user__is_active_member=True)
        request = self.context.get("request")
        if request is not None and is_service_desk_staff(request.user):
            org_id = (
                request.query_params.get("organization")
                or request.query_params.get("organization_id")
                or getattr(request, "organization_id", None)
            )
            if org_id:
                members = members.filter(user__organization_id=org_id)
        members = members.order_by("joined_at", "user__first_name", "user__last_name", "user__email")
        return TeamMemberSerializer(members, many=True).data

    def validate_member_ids(self, member_ids):
        if not member_ids:
            return member_ids
        unique_ids = {str(member_id) for member_id in member_ids}
        users = list(User.objects.filter(id__in=unique_ids, is_active=True, is_active_member=True))
        if len(users) != len(unique_ids):
            raise serializers.ValidationError("One or more selected members are not active.")
        if any(not is_service_desk_staff(user) for user in users):
            raise serializers.ValidationError("Team members must be internal resolver users.")
        return member_ids


class TeamCreateSerializer(TeamSerializer):
    class Meta(TeamSerializer.Meta):
        pass

    def create(self, validated_data):
        member_ids = validated_data.pop('member_ids', [])
        request = self.context['request']
        if 'organization' not in validated_data:
            validated_data['organization'] = getattr(request, 'organization', None)
        team = Team.objects.create(**validated_data)
        for user_id in member_ids:
            TeamMember.objects.get_or_create(team=team, user_id=user_id)
        return team


class TeamUpdateSerializer(TeamSerializer):
    class Meta(TeamSerializer.Meta):
        pass

    def update(self, instance, validated_data):
        member_ids = validated_data.pop('member_ids', None)
        team = super().update(instance, validated_data)
        if member_ids is not None:
            # Delete members that were removed from the selection
            TeamMember.objects.filter(team=team).exclude(user_id__in=member_ids).delete()
            # Fetch remaining existing user IDs
            existing_users = {str(uid) for uid in TeamMember.objects.filter(team=team).values_list('user_id', flat=True)}
            # Only create new records for members that don't already exist
            for user_id in member_ids:
                if str(user_id) not in existing_users:
                    TeamMember.objects.create(team=team, user_id=user_id)
        return team
