from django.urls import path
from .views import ApprovalRequestViewSet, ApproverViewSet

urlpatterns = [
    path('requests/', ApprovalRequestViewSet.as_view({'get': 'list', 'post': 'create'}), name='approval-request-list'),
    path('requests/<uuid:pk>/', ApprovalRequestViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='approval-request-detail'),
    path('approvers/', ApproverViewSet.as_view({'get': 'list', 'post': 'create'}), name='approver-list'),
    path('approvers/<uuid:pk>/', ApproverViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='approver-detail'),
]
