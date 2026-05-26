from django.urls import path
from .views import AutomationRuleViewSet

urlpatterns = [
    path('', AutomationRuleViewSet.as_view({'get': 'list', 'post': 'create'}), name='automation-rule-list'),
    path('<uuid:pk>/', AutomationRuleViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='automation-rule-detail'),
]
