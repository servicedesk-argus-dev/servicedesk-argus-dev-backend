from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.common.mixins import OrgQuerysetMixin
from apps.common.responses import success

from .models import Notification
from .realtime import emit_notification_read, emit_notifications_read_all
from .serializers import NotificationSerializer, NotificationUpdateSerializer


def _for_current_org_if_selected(request, queryset):
    org = getattr(request, "organization", None)
    return queryset.filter(organization=org) if org is not None else queryset


def _unread_count_for_request(request):
    return _for_current_org_if_selected(
        request,
        Notification.objects.filter(user=request.user, is_read=False),
    ).count()


class NotificationListView(OrgQuerysetMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type', 'is_read', 'channel']
    queryset = Notification.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(user=self.request.user)
        return queryset.select_related('user')
    
    def get_serializer_class(self):
        return NotificationSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        unread_count = queryset.filter(is_read=False).count()

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        notifications = [
            {
                "id": item["id"],
                "type": item["type"],
                "title": item["title"],
                "message": item["message"],
                "link": item["link"],
                "isRead": item["is_read"],
                "readAt": item["read_at"],
                "channel": item["channel"],
                "createdAt": item["created_at"],
            }
            for item in serializer.data
        ]
        response = self.get_paginated_response({"notifications": notifications, "unreadCount": unread_count})
        if "pagination" in response.data:
            response.data["pagination"]["total"] = response.data["pagination"].pop("count", 0)
            limit = self.paginator.get_page_size(request) or 25
            total = response.data["pagination"]["total"]
            response.data["pagination"]["pages"] = max((total + limit - 1) // limit, 1) if total else 0
        return response


class NotificationDetailView(OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return NotificationUpdateSerializer
        return NotificationSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user).select_related("user")
    
    def perform_update(self, serializer):
        was_unread = not serializer.instance.is_read
        if serializer.validated_data.get('is_read') and was_unread:
            serializer.validated_data['read_at'] = timezone.now()
        notification = serializer.save()
        if was_unread and notification.is_read:
            unread_count = _unread_count_for_request(self.request)
            emit_notification_read(
                self.request.user.id,
                notification.id,
                unread_count=unread_count,
                read_at=notification.read_at,
            )


class MarkAllReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        queryset = _for_current_org_if_selected(
            request,
            Notification.objects.filter(
                user=request.user,
                is_read=False,
            ),
        )
        updated = queryset.update(
            is_read=True,
            read_at=timezone.now(),
        )
        if updated:
            emit_notifications_read_all(request.user.id)
        return success({"count": 0, "updated": updated}, "all notifications marked as read")


class UnreadCountView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = _for_current_org_if_selected(
            request,
            Notification.objects.filter(
                user=request.user,
                is_read=False,
            ),
        ).count()
        return success({"count": count})


class MarkNotificationReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        queryset = _for_current_org_if_selected(
            request,
            Notification.objects.filter(
                pk=pk,
                user=request.user,
            ),
        )
        notification = queryset.first()
        if notification:
            was_unread = not notification.is_read
            notification.is_read = True
            if notification.read_at is None:
                notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
            if was_unread:
                unread_count = _unread_count_for_request(request)
                emit_notification_read(
                    request.user.id,
                    notification.id,
                    unread_count=unread_count,
                    read_at=notification.read_at,
                )
        return success(message="notification marked as read")

from rest_framework import viewsets
from .models import NotificationTemplate
from .serializers import NotificationTemplateSerializer
from apps.common.permissions import IsAdminOrManager

class NotificationTemplateViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)
