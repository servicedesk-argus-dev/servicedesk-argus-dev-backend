from rest_framework import viewsets, permissions
from .models import AutomationRule
from .serializers import AutomationRuleSerializer
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import IsAdminOrManager

class AutomationRuleViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)
