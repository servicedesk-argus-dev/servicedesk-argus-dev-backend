from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import AuditLog
from .serializers import AuditLogSerializer
from apps.common.responses import success
from apps.common.permissions import IsAdminOrManager, is_service_desk_staff


def audit_queryset_for_request(request):
    queryset = AuditLog.objects.select_related("user", "organization").all()
    if is_service_desk_staff(request.user):
        org_id = (
            request.query_params.get("organization")
            or request.query_params.get("organization_id")
            or getattr(request, "organization_id", None)
        )
        return queryset.filter(organization_id=org_id) if org_id else queryset
    organization = getattr(request, "organization", None) or getattr(request.user, "organization", None)
    if not organization:
        return queryset.none()
    return queryset.filter(organization=organization)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def get_queryset(self):
        return audit_queryset_for_request(self.request)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filtering
        action = request.query_params.get('action')
        resource_type = request.query_params.get('resourceType')
        severity = request.query_params.get('severity')
        actor_email = request.query_params.get('actorEmail')
        correlation_id = request.query_params.get('correlationId')
        method = request.query_params.get('method')
        status_code = request.query_params.get('statusCode')
        start_date = request.query_params.get('startDate')
        end_date = request.query_params.get('endDate')
        
        if action:
            queryset = queryset.filter(action__icontains=action)
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        if actor_email:
            queryset = queryset.filter(actor_email__icontains=actor_email)
        if correlation_id:
            queryset = queryset.filter(correlation_id=correlation_id)
        if method:
            queryset = queryset.filter(method=method.upper())
        if status_code:
            queryset = queryset.filter(status_code=status_code)
        if severity:
            severity = severity.upper()
            if severity == "CRITICAL":
                queryset = queryset.filter(status_code__gte=500)
            elif severity == "WARNING":
                queryset = queryset.filter(
                    Q(status_code__gte=400, status_code__lt=500)
                    | Q(action__in=["LOGIN_FAILED", "KEYCLOAK_LOGIN_FAILED", "MFA_FAILED"])
                )
            elif severity == "INFO":
                queryset = queryset.filter(Q(status_code__lt=400) | Q(status_code__isnull=True))
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
            
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return success(serializer.data)

class AuditResourceTypesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    
    def get(self, request):
        types = audit_queryset_for_request(request).values_list('resource_type', flat=True).distinct()
        return success(list(types))

class AuditAnomaliesView(APIView):
    """
    Stub for anomaly detection. In a real system, this would 
    query a separate table or perform real-time analysis.
    """
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    
    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        
        anomalies = []
        five_mins_ago = timezone.now() - timedelta(minutes=5)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        # 1. Bruteforce check: Multiple failed logins for same username/IP
        scoped_queryset = audit_queryset_for_request(request)

        failed_logins = scoped_queryset.filter(
            action="LOGIN_FAILED",
            created_at__gte=five_mins_ago
        ).values('description').annotate(count=Count('id')).filter(count__gt=3)
        
        for fl in failed_logins:
            anomalies.append({
                "type": "BRUTEFORCE_ATTEMPT",
                "severity": "CRITICAL",
                "description": f"Detected {fl['count']} failed login attempts in 5 minutes: {fl['description']}",
                "count": fl['count'],
                "resource": "USER"
            })
            
        # 2. Unusual deletion activity
        deletions = scoped_queryset.filter(
            action__startswith="DELETE",
            created_at__gte=one_hour_ago
        ).values('user__username').annotate(count=Count('id')).filter(count__gt=10)
        
        for d in deletions:
            anomalies.append({
                "type": "MASS_DELETION",
                "severity": "HIGH",
                "description": f"User {d['user__username']} deleted {d['count']} resources in the last hour",
                "count": d['count'],
                "resource": "SYSTEM"
            })
            
        # 3. High Volume API calls (Optional/Simple)
        
        return success({"alerts": anomalies})
