from rest_framework import serializers
from .models import Notification, NotificationTemplate
from apps.accounts.serializers import UserSerializer
from apps.organizations.serializers import OrganizationSerializer


class NotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'type', 'title', 'message', 'link', 'is_read', 'read_at', 'channel', 'organization', 'created_at']
        read_only_fields = ['id', 'created_at']


class NotificationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['is_read', 'read_at']

class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'name', 'subject_template', 'body_template', 'type', 'channel', 'is_active']
        read_only_fields = ['id']
