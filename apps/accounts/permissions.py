from rest_framework import permissions

class HasRBACPermission(permissions.BasePermission):
    """
    Checks if the user has the required permission via their assigned roles.
    To use this, subclass it and define required_permission_code.
    """
    required_permission_code = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if getattr(request.user, 'is_superuser', False):
            return True

        if not self.required_permission_code:
            return True

        # Check if any of the user's roles have the required permission
        # In a production scenario, we'd cache this at the user/session level
        has_perm = request.user.roles.filter(
            permissions__code=self.required_permission_code
        ).exists()
        
        return has_perm

# Common Permission Classes
class CanManageIncidents(HasRBACPermission):
    required_permission_code = "incident.manage"

class CanCreateIncidents(HasRBACPermission):
    required_permission_code = "incident.create"

class CanManageProblems(HasRBACPermission):
    required_permission_code = "problem.manage"

class CanManageChanges(HasRBACPermission):
    required_permission_code = "change.manage"

class CanManageUsers(HasRBACPermission):
    required_permission_code = "admin.user.manage"
