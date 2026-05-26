from django.urls import path
from .views import WorkflowViewSet, WorkflowStateViewSet, WorkflowTransitionViewSet

urlpatterns = [
    path('', WorkflowViewSet.as_view({'get': 'list', 'post': 'create'}), name='workflow-list'),
    path('<uuid:pk>/', WorkflowViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='workflow-detail'),
    path('states/', WorkflowStateViewSet.as_view({'get': 'list', 'post': 'create'}), name='workflow-state-list'),
    path('states/<uuid:pk>/', WorkflowStateViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='workflow-state-detail'),
    path('transitions/', WorkflowTransitionViewSet.as_view({'get': 'list', 'post': 'create'}), name='workflow-transition-list'),
    path('transitions/<uuid:pk>/', WorkflowTransitionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='workflow-transition-detail'),
]
