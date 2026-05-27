from rest_framework import serializers
from .models import Alert
from apps.accounts.serializers import UserSerializer
from apps.organizations.serializers import OrganizationSerializer


class AlertSerializer(serializers.ModelSerializer):
    acknowledged_by = UserSerializer(read_only=True)
    config_item = serializers.SerializerMethodField()
    incident = serializers.SerializerMethodField()
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'alert_id', 'name', 'severity', 'status', 'source',
            'description', 'metric', 'current_value', 'threshold', 'labels',
            'annotations', 'config_item', 'incident', 'fired_at', 'resolved_at',
            'acknowledged_at', 'acknowledged_by', 'silence_until', 'organization',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_config_item(self, obj):
        if obj.config_item:
            return {'id': str(obj.config_item.id), 'name': obj.config_item.name}
        return None

    def get_incident(self, obj):
        if obj.incident:
            return {'id': str(obj.incident.id), 'number': obj.incident.number, 'short_description': obj.incident.short_description}
        return None


class AlertUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ['status', 'acknowledged_by', 'silence_until']
