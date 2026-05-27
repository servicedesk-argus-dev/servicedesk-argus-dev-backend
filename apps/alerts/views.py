from datetime import timedelta

from django.utils import timezone
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from apps.common.mixins import OrgQuerysetMixin
from apps.common.responses import success, failure
from .models import Alert
from .serializers import AlertSerializer, AlertUpdateSerializer


class AlertListCreateView(OrgQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['severity', 'status', 'source']
    queryset = Alert.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(alert_id__icontains=search) | 
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset.select_related('acknowledged_by', 'config_item', 'incident')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AlertSerializer
        return AlertSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert = serializer.save(organization=request.organization)
        return success(AlertSerializer(alert).data, "alert created", 201)


class AlertDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Alert.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AlertUpdateSerializer
        return AlertSerializer

    def get_queryset(self):
        return super().get_queryset().select_related('acknowledged_by', 'config_item', 'incident')


class AlertStatsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        queryset = Alert.objects.filter(organization=request.organization)
        
        stats = {
            'total': queryset.count(),
            'firing': queryset.filter(status='FIRING').count(),
            'resolved': queryset.filter(status='RESOLVED').count(),
            'acknowledged': queryset.filter(status='ACKNOWLEDGED').count(),
            'critical': queryset.filter(severity='CRITICAL').count(),
            'warning': queryset.filter(severity='WARNING').count(),
            'info': queryset.filter(severity='INFO').count(),
        }
        
        return success(stats)


class AlertKnowledgeBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.problems.models import Problem

        known_errors = (
            Problem.objects.filter(
                organization=request.organization,
                state=Problem.State.KNOWN_ERROR,
            )
            .select_related("assignment_group")
            .order_by("-updated_at", "-created_at")[:50]
        )

        data = [
            {
                "id": str(problem.id),
                "problemId": str(problem.id),
                "number": problem.number,
                "title": problem.short_description,
                "shortDescription": problem.short_description,
                "priority": problem.priority,
                "category": problem.category,
                "workaround": problem.workaround,
                "updatedAt": (problem.updated_at or problem.created_at).isoformat()
                if (problem.updated_at or problem.created_at)
                else None,
            }
            for problem in known_errors
        ]

        return success(data)


class AlertAcknowledgeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        alert = Alert.objects.filter(pk=pk, organization=request.organization).first()
        if alert is None:
            return failure("alert not found", status_code=404)

        alert.status = Alert.Status.ACKNOWLEDGED
        alert.acknowledged_at = timezone.now()
        alert.acknowledged_by = request.user
        alert.save(update_fields=["status", "acknowledged_at", "acknowledged_by", "updated_at"])
        return success(AlertSerializer(alert).data, "alert acknowledged")


class AlertSilenceView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        alert = Alert.objects.filter(pk=pk, organization=request.organization).first()
        if alert is None:
            return failure("alert not found", status_code=404)

        duration_minutes = int(request.data.get("duration", 60) or 60)
        alert.status = Alert.Status.SILENCED
        alert.silence_until = timezone.now() + timedelta(minutes=duration_minutes)
        alert.save(update_fields=["status", "silence_until", "updated_at"])
        return success(AlertSerializer(alert).data, "alert silenced")


class AlertCreateIncidentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.incidents.models import Incident

        alert = Alert.objects.filter(pk=pk, organization=request.organization).first()
        if alert is None:
            return failure("alert not found", status_code=404)

        if alert.incident_id:
            return success(
                {"id": str(alert.incident.id), "number": alert.incident.number},
                "incident already exists",
            )

        severity_map = {
            Alert.Severity.CRITICAL: {
                "impact": Incident.Impact.ENTERPRISE,
                "urgency": Incident.Urgency.CRITICAL,
                "priority": Incident.Priority.P1,
            },
            Alert.Severity.WARNING: {
                "impact": Incident.Impact.TEAM,
                "urgency": Incident.Urgency.HIGH,
                "priority": Incident.Priority.P2,
            },
            Alert.Severity.INFO: {
                "impact": Incident.Impact.INDIVIDUAL,
                "urgency": Incident.Urgency.MEDIUM,
                "priority": Incident.Priority.P3,
            },
        }
        mapped = severity_map.get(alert.severity, severity_map[Alert.Severity.WARNING])

        number = f"INC{timezone.now().year}{timezone.now().strftime('%H%M%S')}{str(alert.id.int)[-4:]}"
        incident = Incident.objects.create(
            number=number,
            short_description=alert.name,
            description=alert.description or f"Created from alert {alert.alert_id}",
            state=Incident.State.NEW,
            impact=mapped["impact"],
            urgency=mapped["urgency"],
            priority=mapped["priority"],
            category=alert.metric or "Alert",
            created_by=request.user,
            config_item=alert.config_item,
            source=Incident.Source.API,
            source_alert_id=alert.alert_id,
            source_alert_name=alert.name,
            organization=request.organization,
        )
        alert.incident = incident
        alert.save(update_fields=["incident", "updated_at"])
        return success({"id": str(incident.id), "number": incident.number}, "incident created", 201)
