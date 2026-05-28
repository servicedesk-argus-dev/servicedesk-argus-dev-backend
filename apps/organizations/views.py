from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import can_manage_clients, is_service_desk_staff
from apps.common.responses import failure
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

    def create(self, request, *args, **kwargs):
        if not can_manage_clients(request.user):
            return failure("Only admins can create clients.", status_code=403)

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return failure("Validation failed.", errors=serializer.errors, status_code=400)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not can_manage_clients(request.user):
            return failure("Only admins can update clients.", status_code=403)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return failure("Validation failed.", errors=serializer.errors, status_code=400)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

