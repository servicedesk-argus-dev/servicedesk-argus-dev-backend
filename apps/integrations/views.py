from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import DenyViewerMutations, IsAdminOrManager, is_service_desk_staff
from apps.common.responses import success
from .models import Integration
from .serializers import IntegrationSerializer

class IntegrationListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    queryset = Integration.objects.all()
    serializer_class = IntegrationSerializer

    def perform_create(self, serializer):
        if not IsAdminOrManager().has_permission(self.request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only admins and managers can create integrations.")
        organization = serializer.validated_data.get("organization") or self.request.organization
        if not is_service_desk_staff(self.request.user):
            organization = self.request.organization
        if organization is None:
            raise ValidationError({"organization_id": "Choose the client organization for this integration."})
        serializer.save(organization=organization)

class IntegrationDetailView(OrgQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]
    queryset = Integration.objects.all()
    serializer_class = IntegrationSerializer

    def perform_update(self, serializer):
        if not IsAdminOrManager().has_permission(self.request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only admins and managers can update integrations.")
        if serializer.validated_data.get("organization") is not None and not is_service_desk_staff(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only service desk admins can move integrations between clients.")
        serializer.save()


class IntegrationTestView(OrgQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def post(self, request, pk):
        queryset = Integration.objects.all()
        if not is_service_desk_staff(request.user):
            if not getattr(request, "organization_id", None):
                raise NotFound("Integration not found.")
            queryset = queryset.filter(organization_id=request.organization_id)

        try:
            integration = queryset.get(pk=pk)
        except Integration.DoesNotExist:
            raise NotFound("Integration not found.")

        config = integration.config or {}
        if not isinstance(config, dict):
            config = {"raw": config}

        required = self._required_config_keys(integration.type, config)
        if required:
            return success({
                "connected": False,
                "message": f"Missing required configuration: {', '.join(required)}",
                "checked": list(config.keys()),
            })

        return success({
            "connected": True,
            "message": "Configuration looks valid. Live network check can be added after credentials are finalized.",
            "checked": list(config.keys()),
        })

    def _required_config_keys(self, integration_type, config):
        def has_any(*keys):
            return any(config.get(key) for key in keys)

        missing = []
        if integration_type == "SLACK" and not has_any("webhookUrl", "webhook_url", "botToken", "bot_token"):
            missing.append("webhookUrl or botToken")
        elif integration_type == "WEBHOOK" and not has_any("url", "webhookUrl", "webhook_url"):
            missing.append("url")
        elif integration_type == "EMAIL" and not has_any("smtpHost", "smtp_host", "host"):
            missing.append("smtpHost")
        elif integration_type == "PROMETHEUS" and not has_any("prometheusUrl", "prometheus_url", "serverIp", "server_ip"):
            missing.append("prometheusUrl or serverIp")
        elif integration_type == "GRAFANA" and not has_any("grafanaExternalUrl", "grafanaUrl", "grafana_url"):
            missing.append("grafanaUrl")
        elif integration_type == "KUBERNETES_CLUSTER" and not has_any("k8sApiUrl", "k8s_api_url", "serverIp", "server_ip"):
            missing.append("k8sApiUrl or serverIp")
        return missing
