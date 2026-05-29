"""Production RBAC helpers.

Keycloak is the source of truth for SSO users. Argus stores a small cache of
Keycloak roles and permission codes on the user so API checks stay fast and
auditable. Local Argus roles still work as a compatibility fallback.
"""

from __future__ import annotations

from collections.abc import Iterable

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import User


class Roles:
    SUPER_ADMIN = "Super Admin"
    ORG_ADMIN = "Org Admin"
    MANAGER = "Manager"
    ENGINEER = "Engineer"
    TEAM_LEAD = "Team Lead"
    NOC = "NOC"
    CLIENT_USER = "Client User"
    OPERATOR = "Operator"
    VIEWER = "Viewer"


ROLE_TOKEN_NAMES = {
    "ADMIN",
    "SUPER_ADMIN",
    "ORG_ADMIN",
    "MANAGER",
    "ENGINEER",
    "TEAM_LEAD",
    "NOC",
    "CLIENT_USER",
    "OPERATOR",
    "VIEWER",
}

ROLE_TOKEN_TO_NAME = {
    "ADMIN": Roles.ORG_ADMIN,
    "SUPER_ADMIN": Roles.SUPER_ADMIN,
    "ORG_ADMIN": Roles.ORG_ADMIN,
    "MANAGER": Roles.MANAGER,
    "ENGINEER": Roles.ENGINEER,
    "TEAM_LEAD": Roles.TEAM_LEAD,
    "NOC": Roles.NOC,
    "CLIENT_USER": Roles.CLIENT_USER,
    "OPERATOR": Roles.OPERATOR,
    "VIEWER": Roles.VIEWER,
}

ROLE_NAME_TO_TOKEN = {value: key for key, value in ROLE_TOKEN_TO_NAME.items()}


def role_token_name(role_name: object) -> str:
    raw = str(role_name or "").strip()
    if not raw:
        return ""
    return raw.upper().replace("-", "_").replace(" ", "_")


def canonical_role_name(role_name: object) -> str:
    raw = str(role_name or "").strip()
    if not raw:
        return ""
    return ROLE_TOKEN_TO_NAME.get(role_token_name(raw), raw)


IGNORED_KEYCLOAK_ROLES = {
    "offline_access",
    "uma_authorization",
}

INTERNAL_ROLE_NAMES = {
    Roles.SUPER_ADMIN,
    Roles.ORG_ADMIN,
    Roles.MANAGER,
    Roles.ENGINEER,
    Roles.TEAM_LEAD,
    Roles.NOC,
    Roles.OPERATOR,
}

ADMIN_ROLE_NAMES = {
    Roles.SUPER_ADMIN,
    Roles.ORG_ADMIN,
    Roles.MANAGER,
    Roles.TEAM_LEAD,
    Roles.NOC,
}

PERMISSION_ALIASES = {
    "incident.manage": "incident:manage",
    "problem.manage": "problem:manage",
    "change.manage": "change:manage",
    "admin.user.manage": "user:manage",
    "admin.role.manage": "role:manage",
    "admin.team.manage": "team:manage",
    "knowledge.manage": "kb:manage",
    "knowledge.read": "kb:read",
    "catalog.manage": "catalog:manage",
    "learning.manage": "learning:manage",
    "learning.read": "learning:read",
}

READ_PERMISSIONS = frozenset(
    {
        "incident:read",
        "problem:read",
        "change:read",
        "service_request:read",
        "catalog:read",
        "kb:read",
        "asset:read",
        "team:read",
        "user:read",
        "client:read",
        "sla:read",
        "report:read",
        "audit:read",
    }
)

CLIENT_PERMISSIONS = frozenset(
    {
        "incident:read",
        "incident:create",
        "problem:read",
        "problem:create",
        "change:read",
        "change:create",
        "service_request:read",
        "service_request:create",
        "service_request:close",
        "service_request:reopen",
        "catalog:read",
        "kb:read",
        "comment:create",
        "attachment:create",
    }
)

ENGINEER_PERMISSIONS = READ_PERMISSIONS | frozenset(
    {
        "learning:read",
        "learning:complete",
        "incident:create",
        "incident:update",
        "incident:resolve",
        "incident:reopen",
        "problem:create",
        "problem:update",
        "problem:resolve",
        "problem:rca",
        "change:create",
        "change:update",
        "service_request:create",
        "service_request:update",
        "service_request:fulfill",
        "comment:create",
        "attachment:create",
        "work_note:create",
    }
)

NOC_PERMISSIONS = READ_PERMISSIONS | frozenset(
    {
        "learning:read",
        "learning:complete",
        "learning:assign",
        "incident:create",
        "incident:update",
        "incident:assign",
        "incident:escalate",
        "incident:link",
        "problem:create",
        "problem:update",
        "problem:assign",
        "problem:link",
        "problem:rca",
        "change:create",
        "change:update",
        "change:assign",
        "change:link",
        "service_request:update",
        "service_request:approve",
        "service_request:assign",
        "team:read",
        "comment:create",
        "attachment:create",
        "work_note:create",
    }
)

MANAGER_PERMISSIONS = READ_PERMISSIONS | frozenset(
    {
        "learning:*",
        "incident:*",
        "problem:*",
        "change:*",
        "service_request:*",
        "catalog:manage",
        "kb:manage",
        "asset:manage",
        "team:manage",
        "user:read",
        "sla:manage",
        "report:read",
        "audit:read",
        "comment:create",
        "attachment:create",
        "work_note:create",
    }
)

ORG_ADMIN_PERMISSIONS = MANAGER_PERMISSIONS | frozenset(
    {
        "client:read",
        "client:manage",
        "user:manage",
        "role:read",
        "role:manage",
        "settings:read",
    }
)

ROLE_DEFAULT_PERMISSIONS = {
    Roles.SUPER_ADMIN: frozenset({"*:*"}),
    Roles.ORG_ADMIN: ORG_ADMIN_PERMISSIONS,
    Roles.MANAGER: MANAGER_PERMISSIONS,
    Roles.TEAM_LEAD: MANAGER_PERMISSIONS,
    Roles.NOC: NOC_PERMISSIONS,
    Roles.OPERATOR: NOC_PERMISSIONS,
    Roles.ENGINEER: ENGINEER_PERMISSIONS,
    Roles.CLIENT_USER: CLIENT_PERMISSIONS,
    Roles.VIEWER: READ_PERMISSIONS,
}

INTERNAL_STAFF_PERMISSIONS = frozenset(
    {
        "incident:update",
        "incident:assign",
        "problem:update",
        "problem:assign",
        "change:update",
        "change:assign",
        "service_request:fulfill",
        "service_request:approve",
        "learning:read",
        "learning:complete",
        "team:read",
    }
)

SERVICE_DESK_MANAGE_PERMISSIONS = frozenset(
    {
        "incident:assign",
        "incident:manage",
        "problem:assign",
        "problem:manage",
        "change:assign",
        "change:manage",
        "service_request:assign",
        "service_request:approve",
        "service_request:manage",
        "team:manage",
    }
)

USER_MANAGE_PERMISSIONS = frozenset({"user:manage", "role:manage", "settings:manage"})


def normalize_permission_code(code: object) -> str:
    raw = str(code or "").strip()
    if not raw:
        return ""

    alias = PERMISSION_ALIASES.get(raw) or PERMISSION_ALIASES.get(raw.lower())
    if alias:
        raw = alias

    raw = raw.strip().replace(" ", "_")
    if ":" not in raw and "." in raw:
        parts = [part for part in raw.split(".") if part]
        if len(parts) >= 2:
            raw = f"{'_'.join(parts[:-1])}:{parts[-1]}"
    return raw.lower()


def permission_code_from_keycloak_role(role_name: object) -> str:
    raw = str(role_name or "").strip()
    if not raw:
        return ""

    if raw.lower().startswith("default-roles-"):
        return ""
    if raw.lower() in IGNORED_KEYCLOAK_ROLES:
        return ""
    if role_token_name(raw) in ROLE_TOKEN_NAMES:
        return ""

    permission_code = normalize_permission_code(raw)
    if ":" not in permission_code:
        return ""
    resource, action = permission_code.split(":", 1)
    if not resource or not action:
        return ""
    return permission_code


def _iter_normalized(codes: Iterable[object]) -> set[str]:
    return {code for code in (normalize_permission_code(value) for value in codes) if code}


def _role_default_permissions(user: User) -> set[str]:
    if getattr(user, "is_superuser", False):
        return {"*:*"}

    try:
        role_names = list(user.role_names)
    except Exception:
        role_names = []

    permissions: set[str] = set()
    for role_name in role_names:
        permissions.update(ROLE_DEFAULT_PERMISSIONS.get(canonical_role_name(role_name), ()))
    return permissions


def _local_role_permissions(user: User) -> set[str]:
    try:
        return _iter_normalized(
            code for code in user.roles.values_list("permissions__code", flat=True) if code
        )
    except Exception:
        return set()


def user_permission_codes(user: User) -> frozenset[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return frozenset()

    cached = getattr(user, "_argus_permission_codes", None)
    if cached is not None:
        return cached

    permissions = set()
    permissions.update(_iter_normalized(getattr(user, "keycloak_permissions", []) or []))
    permissions.update(_local_role_permissions(user))
    permissions.update(_role_default_permissions(user))

    result = frozenset(permissions)
    setattr(user, "_argus_permission_codes", result)
    return result


def user_has_permission(user: User, permission_code: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    required = normalize_permission_code(permission_code)
    if not required:
        return True

    permissions = user_permission_codes(user)
    if "*:*" in permissions or "*" in permissions or required in permissions:
        return True

    if ":" in required:
        resource, _action = required.split(":", 1)
        if f"{resource}:*" in permissions:
            return True

    return False


def user_has_any_permission(user: User, *permission_codes: str) -> bool:
    return any(user_has_permission(user, code) for code in permission_codes)


def has_any_role(user: User, *role_names: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return any(user.has_role(role_name) for role_name in role_names)


def is_service_desk_staff(user: User) -> bool:
    return has_any_role(user, *INTERNAL_ROLE_NAMES) or user_has_any_permission(
        user,
        *INTERNAL_STAFF_PERMISSIONS,
    )


def can_manage_service_desk(user: User) -> bool:
    return has_any_role(user, *ADMIN_ROLE_NAMES) or user_has_any_permission(
        user,
        *SERVICE_DESK_MANAGE_PERMISSIONS,
    )


def can_manage_users(user: User) -> bool:
    return has_any_role(user, Roles.SUPER_ADMIN, Roles.ORG_ADMIN, Roles.MANAGER) or user_has_any_permission(
        user,
        *USER_MANAGE_PERMISSIONS,
    )


def can_manage_clients(user: User) -> bool:
    return has_any_role(user, Roles.SUPER_ADMIN, Roles.ORG_ADMIN) or user_has_permission(user, "client:manage")


def is_assigned_to_service_record(user: User, obj) -> bool:
    """Return true when the user owns the record directly or through its team."""
    if not user or not getattr(user, "is_authenticated", False) or obj is None:
        return False
    if getattr(obj, "assigned_to_id", None) == user.id:
        return True

    assignment_group = getattr(obj, "assignment_group", None)
    if not assignment_group:
        return False
    try:
        return assignment_group.members.filter(user=user).exists()
    except Exception:
        return False


def _record_resource(obj) -> str:
    model_name = getattr(getattr(obj, "_meta", None), "model_name", "")
    return {
        "incident": "incident",
        "problem": "problem",
        "change": "change",
        "servicerequest": "service_request",
    }.get(model_name, model_name)


def user_has_record_permission(user: User, obj, *actions: str) -> bool:
    resource = _record_resource(obj)
    if not resource:
        return False
    permission_codes = [f"{resource}:{action}" for action in actions]
    permission_codes.extend([f"{resource}:manage", f"{resource}:*"])
    return user_has_any_permission(user, *permission_codes)


def can_assign_service_record(user: User, obj) -> bool:
    return has_any_role(user, *ADMIN_ROLE_NAMES) or user_has_record_permission(user, obj, "assign")


def can_edit_service_record(user: User, obj) -> bool:
    if can_assign_service_record(user, obj):
        return True
    if not is_service_desk_staff(user):
        return False

    if not user_has_record_permission(user, obj, "update"):
        return False
    return is_assigned_to_service_record(user, obj)


class DenyViewerMutations(BasePermission):
    """VIEWER may only use safe HTTP methods unless Keycloak grants write access."""

    message = "Viewers have read-only access."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if not request.user.has_role(Roles.VIEWER):
            return True
        return user_has_any_permission(
            request.user,
            "incident:create",
            "incident:update",
            "problem:create",
            "problem:update",
            "change:create",
            "change:update",
            "service_request:create",
            "service_request:update",
        )


class IncidentTransitionRBAC(BasePermission):
    """Incident lifecycle permissions backed by Keycloak permission roles."""

    message = "Your role cannot perform this incident transition."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        new_state = request.data.get("state", obj.state)
        if new_state == obj.state:
            return user_has_any_permission(user, "incident:update", "incident:assign", "incident:manage")

        if new_state == "ESCALATED":
            return user_has_any_permission(user, "incident:escalate", "incident:update", "incident:manage")
        if new_state == "RESOLVED":
            return user_has_any_permission(user, "incident:resolve", "incident:manage")
        if new_state in {"CLOSED", "CANCELLED"}:
            return user_has_any_permission(user, "incident:close", "incident:manage")
        if obj.state in {"RESOLVED", "CLOSED"} and new_state == "IN_PROGRESS":
            return user_has_any_permission(user, "incident:reopen", "incident:manage")
        return user_has_any_permission(user, "incident:update", "incident:manage")


class ProblemTransitionRBAC(BasePermission):
    """Problem lifecycle permissions backed by Keycloak permission roles."""

    message = "Your role cannot perform this problem transition."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        new_state = request.data.get("state", obj.state)
        if new_state == obj.state:
            return user_has_any_permission(user, "problem:update", "problem:assign", "problem:manage")
        if new_state == "RESOLVED":
            return user_has_any_permission(user, "problem:resolve", "problem:manage")
        if new_state == "CLOSED":
            return user_has_any_permission(user, "problem:close", "problem:manage")
        if obj.state in {"RESOLVED", "CLOSED"} and new_state == "INVESTIGATION":
            return user_has_any_permission(user, "problem:reopen", "problem:manage")
        return user_has_any_permission(user, "problem:update", "problem:manage")


class ChangeTransitionRBAC(BasePermission):
    """Change lifecycle permissions backed by Keycloak permission roles."""

    message = "Your role cannot perform this change transition."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        new_state = request.data.get("state", obj.state)
        if new_state == obj.state:
            return user_has_any_permission(user, "change:update", "change:assign", "change:manage")
        if new_state == "APPROVAL":
            return user_has_any_permission(user, "change:update", "change:approve", "change:manage")
        if new_state == "CLOSED":
            return user_has_any_permission(user, "change:close", "change:manage")
        if new_state == "CANCELLED":
            return user_has_any_permission(user, "change:cancel", "change:manage")
        return user_has_any_permission(user, "change:update", "change:manage")


class ChangeApprovalRBAC(BasePermission):
    """Approvals and approval decisions are restricted to Keycloak approvers."""

    message = "Only change approvers can manage change approvals."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return user_has_any_permission(request.user, "change:approve", "change:manage")


class IsAdminOrManager(BasePermission):
    """Administrative mutating actions."""

    message = "Only authorized admins and managers have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return can_manage_service_desk(user) or user_has_any_permission(
            user,
            "asset:manage",
            "team:manage",
            "user:manage",
            "settings:manage",
        )


class IsOrgMember(BasePermission):
    """User must belong to the organization being accessed."""

    message = "You do not belong to this organization."

    def has_permission(self, request, view) -> bool:
        user_org = request.user.organization
        if is_service_desk_staff(request.user):
            return True
        if not user_org:
            return False
        return True
