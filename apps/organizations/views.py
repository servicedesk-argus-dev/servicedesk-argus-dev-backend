from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.common.permissions import can_manage_service_desk, is_service_desk_staff
from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Organization.objects.all().order_by("name")
        if is_service_desk_staff(self.request.user):
            return queryset
        if getattr(self.request, "organization_id", None):
            return queryset.filter(id=self.request.organization_id)
        return queryset.none()

    def perform_create(self, serializer):
        if not can_manage_service_desk(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only service desk admins can create clients.")
        serializer.save()

    def perform_update(self, serializer):
        if not can_manage_service_desk(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only service desk admins can update clients.")
        serializer.save()

