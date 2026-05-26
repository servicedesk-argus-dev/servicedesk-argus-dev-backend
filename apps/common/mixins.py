from rest_framework.exceptions import PermissionDenied

from apps.common.permissions import is_service_desk_staff


class OrgQuerysetMixin:
    organization_lookup = "organization"

    def get_queryset(self):
        queryset = super().get_queryset()
        organization = getattr(self.request, "organization", None) or getattr(self.request.user, "organization", None)
        if is_service_desk_staff(self.request.user):
            org_id = (
                self.request.query_params.get("organization")
                or self.request.query_params.get("organization_id")
                or getattr(self.request, "organization_id", None)
            )
            if org_id:
                return queryset.filter(**{f"{self.organization_lookup}_id": org_id})
            return queryset
        if organization is None:
            raise PermissionDenied("Organization access denied")
        return queryset.filter(**{self.organization_lookup: organization})
