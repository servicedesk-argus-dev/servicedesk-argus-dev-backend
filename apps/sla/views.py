from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import generics

from apps.common.responses import failure, success
from apps.common.permissions import DenyViewerMutations, IsAdminOrManager

from .models import SLADefinition, TaskSLA
from .serializers import SLADefinitionSerializer, TaskSLASerializer
from .services import default_definition_values, ensure_default_definitions


class SLADefinitionListView(APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def get(self, request):
        organization = getattr(request, "organization", None)
        if organization is None:
            return failure("Organization context required.", status_code=400)

        applies_to = request.query_params.get("appliesTo") or request.query_params.get("applies_to") or SLADefinition.AppliesTo.INCIDENT
        if applies_to not in SLADefinition.AppliesTo.values:
            return failure("Invalid appliesTo value.", status_code=400)

        ensure_default_definitions(organization, applies_to)
        queryset = SLADefinition.objects.filter(organization=organization, applies_to=applies_to).order_by("priority")
        return success(SLADefinitionSerializer(queryset, many=True).data)


class SLADefinitionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def patch(self, request, priority):
        organization = getattr(request, "organization", None)
        if organization is None:
            return failure("Organization context required.", status_code=400)

        priority = priority.upper()
        if priority not in SLADefinition.Priority.values:
            return failure("Invalid SLA priority.", status_code=400)

        applies_to = request.data.get("appliesTo") or request.data.get("applies_to") or SLADefinition.AppliesTo.INCIDENT
        if applies_to not in SLADefinition.AppliesTo.values:
            return failure("Invalid appliesTo value.", status_code=400)

        definition, _created = SLADefinition.objects.get_or_create(
            organization=organization,
            applies_to=applies_to,
            priority=priority,
            defaults=default_definition_values(priority, applies_to),
        )

        payload = request.data.copy()
        if "response_time_minutes" in payload and "responseTimeMinutes" not in payload:
            payload["responseTimeMinutes"] = payload["response_time_minutes"]
        if "resolution_time_minutes" in payload and "resolutionTimeMinutes" not in payload:
            payload["resolutionTimeMinutes"] = payload["resolution_time_minutes"]
        if "business_hours_only" in payload and "businessHoursOnly" not in payload:
            payload["businessHoursOnly"] = payload["business_hours_only"]
        if "is_active" in payload and "isActive" not in payload:
            payload["isActive"] = payload["is_active"]

        serializer = SLADefinitionSerializer(definition, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success(serializer.data, "SLA definition updated.")


class TaskSLAListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSLASerializer

    def get_queryset(self):
        incident_id = self.kwargs.get('incident_id')
        return TaskSLA.objects.filter(
            incident_id=incident_id,
            incident__organization=self.request.organization
        ).order_by('start_time')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return success(serializer.data)

