from django.urls import path
from .audit_views import AuditLogViewSet, AuditResourceTypesView, AuditAnomaliesView

urlpatterns = [
    path('logs/', AuditLogViewSet.as_view({'get': 'list'}), name='audit-log-list'),
    path('logs/<uuid:pk>/', AuditLogViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='audit-log-detail'),
    path('resource-types/', AuditResourceTypesView.as_view(), name='audit-resource-types'),
    path('anomalies/', AuditAnomaliesView.as_view(), name='audit-anomalies'),
]
