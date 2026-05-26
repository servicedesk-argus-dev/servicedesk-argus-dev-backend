from rest_framework import viewsets, generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from .models import AuditLog
from .serializers import AuditLogSerializer
from apps.common.responses import success
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import IsAdminOrManager

class AuditLogViewSet(OrgQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filtering
        action = request.query_params.get('action')
        resource_type = request.query_params.get('resourceType')
        severity = request.query_params.get('severity')
        start_date = request.query_params.get('startDate')
        end_date = request.query_params.get('endDate')
        
        if action:
            queryset = queryset.filter(action__icontains=action)
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
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
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        types = AuditLog.objects.filter(
            organization=request.organization
        ).values_list('resource_type', flat=True).distinct()
        return success(list(types))

class AuditAnomaliesView(APIView):
    """
    Stub for anomaly detection. In a real system, this would 
    query a separate table or perform real-time analysis.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        
        anomalies = []
        five_mins_ago = timezone.now() - timedelta(minutes=5)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        # 1. Bruteforce check: Multiple failed logins for same username/IP
        failed_logins = AuditLog.objects.filter(
            organization=request.organization,
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
        deletions = AuditLog.objects.filter(
            organization=request.organization,
            action="DELETE",
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
