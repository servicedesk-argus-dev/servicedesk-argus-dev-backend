from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers

from apps.common.permissions import (
    Roles,
    canonical_role_name,
    is_service_desk_staff,
    user_has_any_permission,
    user_has_permission,
    user_permission_codes,
)
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer
from .models import Permission, Role

User = get_user_model()


ROLE_TO_FRONTEND = {
    Roles.SUPER_ADMIN: "ADMIN",
    Roles.ORG_ADMIN: "ADMIN",
    Roles.MANAGER: "MANAGER",
    Roles.TEAM_LEAD: "MANAGER",
    Roles.NOC: "OPERATOR",
    Roles.ENGINEER: "ENGINEER",
    Roles.CLIENT_USER: "CLIENT",
    Roles.OPERATOR: "OPERATOR",
    Roles.VIEWER: "VIEWER",
}

CLIENT_ROLE_NAMES = {Roles.CLIENT_USER, Roles.VIEWER}
INTERNAL_ROLE_NAMES = {
    Roles.SUPER_ADMIN,
    Roles.ORG_ADMIN,
    Roles.MANAGER,
    Roles.TEAM_LEAD,
    Roles.NOC,
    Roles.ENGINEER,
    Roles.OPERATOR,
}

DEFAULT_ROLE_DESCRIPTIONS = {
    Roles.SUPER_ADMIN: "FinSpot admin with access to all clients and records.",
    Roles.ORG_ADMIN: "Internal service-desk admin for client, user, team, queue, and ticket administration.",
    Roles.CLIENT_USER: "Client portal user scoped to one organization.",
    Roles.ENGINEER: "Internal resolver who works assigned tickets.",
    Roles.TEAM_LEAD: "Internal lead who manages team queues and assignments.",
    Roles.NOC: "NOC/L1 triage user for new and unassigned incidents.",
    Roles.MANAGER: "Service desk manager.",
    Roles.OPERATOR: "Service desk operator.",
    Roles.VIEWER: "Read-only user.",
}


def ensure_role(role_name: str) -> Role:
    role_name = canonical_role_name(role_name)
    return Role.objects.get_or_create(
        name=role_name,
        defaults={
            "description": DEFAULT_ROLE_DESCRIPTIONS.get(role_name, ""),
            "is_system": role_name in DEFAULT_ROLE_DESCRIPTIONS,
        },
    )[0]


def _team_queryset_for_request(request):
    from apps.teams.models import Team

    queryset = Team.objects.filter(is_active=True)
    if request is None:
        return Team.objects.none()
    if is_service_desk_staff(request.user):
        return queryset
    organization = getattr(request, "organization", None) or getattr(request.user, "organization", None)
    if organization is None:
        return Team.objects.none()
    return queryset.filter(Q(organization=organization) | Q(organization__isnull=True))


def _resolve_team_ids(request, team_ids):
    if not team_ids:
        return []
    unique_ids = {str(team_id) for team_id in team_ids}
    teams = list(_team_queryset_for_request(request).filter(id__in=unique_ids))
    if len(teams) != len(unique_ids):
        raise serializers.ValidationError({"team_ids": "One or more selected teams are not available."})
    return teams


def _sync_user_teams(user, teams):
    from apps.teams.models import TeamMember

    TeamMember.objects.filter(user=user).delete()
    for team in teams:
        TeamMember.objects.get_or_create(team=team, user=user)


def primary_role_name(user) -> str:
    names = [canonical_role_name(name) for name in user.role_names]
    if names:
        return names[0]
    if getattr(user, "is_superuser", False):
        return Roles.SUPER_ADMIN
    return ""


def frontend_role(user) -> str:
    role = ROLE_TO_FRONTEND.get(primary_role_name(user))
    if role:
        return role
    if user_has_any_permission(user, "user:manage", "settings:manage", "*:*"):
        return "ADMIN"
    if user_has_any_permission(user, "incident:assign", "problem:assign", "change:assign", "team:manage"):
        return "MANAGER"
    if user_has_any_permission(user, "incident:update", "problem:update", "change:update", "service_request:fulfill"):
        return "ENGINEER"
    if user_has_any_permission(user, "incident:create", "service_request:create"):
        return "CLIENT"
    return "VIEWER"


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "code", "description", "created_at")


class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        required=False,
        queryset=Permission.objects.all(),
        source="permissions",
    )

    class Meta:
        model = Role
        fields = ("id", "name", "description", "permissions", "permission_ids", "is_system")


class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    role_names = serializers.SerializerMethodField()
    roleNames = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    permissionCodes = serializers.SerializerMethodField()
    teamMemberships = serializers.SerializerMethodField()
    role_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        required=False,
        queryset=Role.objects.all(),
        source="roles",
    )
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        source="organization",
        write_only=True,
        required=False,
        allow_null=True,
    )
    organizationId = serializers.SerializerMethodField()
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)
    mfaEnabled = serializers.BooleanField(source="mfa_enabled", read_only=True)
    mustChangePassword = serializers.BooleanField(source="must_change_password", read_only=True)
    isActiveMember = serializers.BooleanField(source="is_active_member", read_only=True)
    status = serializers.SerializerMethodField()
    avatar = serializers.CharField(source="avatar_url", read_only=True)
    lastLogin = serializers.DateTimeField(source="last_login", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "firstName",
            "last_name",
            "lastName",
            "phone",
            "timezone",
            "roles",
            "role_names",
            "roleNames",
            "role",
            "permissions",
            "permissionCodes",
            "teamMemberships",
            "role_ids",
            "organization",
            "organization_id",
            "organizationId",
            "mfa_enabled",
            "mfaEnabled",
            "must_change_password",
            "mustChangePassword",
            "is_active",
            "is_active_member",
            "isActiveMember",
            "status",
            "avatar_url",
            "avatar",
            "last_login",
            "lastLogin",
            "created_at",
            "createdAt",
            "updated_at",
            "updatedAt",
        )
        read_only_fields = ("id", "created_at", "updated_at", "last_login")

    def get_role_names(self, obj):
        names = [canonical_role_name(name) for name in obj.role_names]
        return names or ([Roles.SUPER_ADMIN] if obj.is_superuser else [])

    def get_roleNames(self, obj):
        return self.get_role_names(obj)

    def get_role(self, obj):
        return frontend_role(obj)

    def get_permissions(self, obj):
        return sorted(user_permission_codes(obj))

    def get_permissionCodes(self, obj):
        return self.get_permissions(obj)

    def get_organizationId(self, obj):
        return str(obj.organization_id) if obj.organization_id else None

    def get_status(self, obj):
        if not obj.is_active or not obj.is_active_member:
            return "INACTIVE"
        return "ACTIVE"

    def get_teamMemberships(self, obj):
        memberships = obj.team_memberships.select_related("team").filter(team__is_active=True).order_by("team__name")
        return [
            {
                "id": str(membership.id),
                "role": membership.role,
                "team": {
                    "id": str(membership.team_id),
                    "name": membership.team.name,
                },
            }
            for membership in memberships
        ]


class ManagedUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    timezone = serializers.CharField(required=False, allow_blank=True)
    role_name = serializers.CharField(default=Roles.CLIENT_USER)
    team_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        source="organization",
    )
    must_change_password = serializers.BooleanField(default=True)
    is_active = serializers.BooleanField(default=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        attrs["email"] = email
        attrs["username"] = (attrs.get("username") or email).strip().lower()
        role_name = canonical_role_name(attrs.get("role_name") or Roles.CLIENT_USER)
        attrs["role_name"] = role_name
        organization = attrs.get("organization")
        team_ids = attrs.get("team_ids", [])
        request_user = getattr(self.context.get("request"), "user", None)

        if role_name in CLIENT_ROLE_NAMES and organization is None:
            raise serializers.ValidationError(
                {"organization_id": "Client users must be linked to a client organization."}
            )
        if role_name in CLIENT_ROLE_NAMES and team_ids:
            raise serializers.ValidationError({"team_ids": "Client users cannot be assigned to resolver teams."})
        _resolve_team_ids(self.context.get("request"), team_ids)

        if role_name in {Roles.SUPER_ADMIN, Roles.ORG_ADMIN} and not user_has_permission(request_user, "*:*"):
            raise serializers.ValidationError(
                {"role_name": "Only a Super Admin can create Admin or Super Admin accounts."}
            )

        if role_name == Roles.SUPER_ADMIN:
            attrs["organization"] = None
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        role_name = validated_data.pop("role_name")
        team_ids = validated_data.pop("team_ids", [])
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        try:
            user.save()
        except IntegrityError as exc:
            message = str(exc).lower()
            if "username" in message or "email" in message or "unique" in message:
                raise serializers.ValidationError(
                    {
                        "email": "An account with this email already exists.",
                        "username": "This username or email is already registered.",
                    }
                )
            raise
        user.roles.add(ensure_role(role_name))
        if role_name not in CLIENT_ROLE_NAMES:
            _sync_user_teams(user, _resolve_team_ids(self.context.get("request"), team_ids))
        return user


class ManagedUserUpdateSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(required=False)
    team_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True),
        source="organization",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone",
            "timezone",
            "email",
            "username",
            "role_name",
            "team_ids",
            "organization_id",
            "is_active",
            "is_active_member",
            "must_change_password",
        )

    def validate(self, attrs):
        if attrs.get("role_name"):
            attrs["role_name"] = canonical_role_name(attrs["role_name"])
        role_name = attrs.get("role_name")
        team_ids = attrs.get("team_ids", None)
        organization = attrs.get("organization", self.instance.organization if self.instance else None)
        if role_name in CLIENT_ROLE_NAMES and organization is None:
            raise serializers.ValidationError(
                {"organization_id": "Client users must be linked to a client organization."}
            )
        if role_name in CLIENT_ROLE_NAMES and team_ids:
            raise serializers.ValidationError({"team_ids": "Client users cannot be assigned to resolver teams."})
        if team_ids is not None:
            _resolve_team_ids(self.context.get("request"), team_ids)
        return attrs

    def update(self, instance, validated_data):
        role_name = validated_data.pop("role_name", None)
        team_ids = validated_data.pop("team_ids", None)
        instance = super().update(instance, validated_data)
        if role_name:
            instance.roles.set([ensure_role(role_name)])
        active_role = role_name or primary_role_name(instance)
        if active_role in CLIENT_ROLE_NAMES:
            _sync_user_teams(instance, [])
        elif team_ids is not None:
            _sync_user_teams(instance, _resolve_team_ids(self.context.get("request"), team_ids))
        return instance


class PasswordSetSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    must_change_password = serializers.BooleanField(default=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    oldPassword = serializers.CharField(write_only=True, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, required=False, min_length=8)
    newPassword = serializers.CharField(write_only=True, required=False, min_length=8)

    def validate(self, attrs):
        new_password = attrs.get("new_password") or attrs.get("newPassword")
        if not new_password:
            raise serializers.ValidationError({"new_password": "New password is required."})
        attrs["new_password"] = new_password
        attrs["current_password"] = attrs.get("current_password") or attrs.get("oldPassword") or ""
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone",
            "timezone",
            "avatar_url",
            "notification_prefs",
        )


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12)
    organization = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "organization")

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        attrs["email"] = email
        username = (attrs.get("username") or email).strip().lower()
        attrs["username"] = username
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        organization_id = validated_data.pop("organization", None)

        if not organization_id:
            org, _created = Organization.objects.get_or_create(
                name="Default Organization",
                defaults={"slug": "default-org"},
            )
            organization_id = org.id

        user = User(**validated_data, organization_id=organization_id)
        user.set_password(password)
        try:
            user.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {
                    "email": "An account with this email already exists.",
                    "username": "This username or email is already registered.",
                }
            )
        user.roles.add(ensure_role(Roles.CLIENT_USER))
        return user


class MeSerializer(UserSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("organization_name",)
