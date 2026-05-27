from django.urls import path
from .views import (
    MarkAllReadView,
    MarkNotificationReadView,
    NotificationDetailView,
    NotificationListView,
    UnreadCountView,
    NotificationTemplateViewSet,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count", UnreadCountView.as_view(), name="notification-unread-count"),
    path("read-all", MarkAllReadView.as_view(), name="notification-read-all"),
    path("<uuid:pk>/read", MarkNotificationReadView.as_view(), name="notification-mark-read"),
    path("<uuid:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
    path("templates/", NotificationTemplateViewSet.as_view({'get': 'list', 'post': 'create'}), name="notification-template-list"),
    path("templates/<uuid:pk>/", NotificationTemplateViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name="notification-template-detail"),
]
