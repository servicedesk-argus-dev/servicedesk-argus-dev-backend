from rest_framework import serializers
from .models import AuditLog
from apps.accounts.serializers import UserSerializer

class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    resourceType = serializers.CharField(source='resource_type', read_only=True)
    resourceId = serializers.CharField(source='resource_id', read_only=True)
    ipAddress = serializers.IPAddressField(source='ip_address', read_only=True)
    userAgent = serializers.CharField(source='user_agent', read_only=True)
    requestPayload = serializers.JSONField(source='request_payload', read_only=True)
    responsePayload = serializers.JSONField(source='response_payload', read_only=True)
    actorEmail = serializers.EmailField(source='actor_email', read_only=True)
    statusCode = serializers.IntegerField(source='status_code', read_only=True)
    correlationId = serializers.CharField(source='correlation_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    status = serializers.SerializerMethodField()
    severity = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'action', 'resource_type', 'resource_id', 
            'description', 'ip_address', 'user_agent', 
            'request_payload', 'response_payload', 'created_at', 'user',
            'actor_email', 'method', 'path', 'status_code', 'correlation_id',
            'resourceType', 'resourceId', 'ipAddress', 'userAgent',
            'requestPayload', 'responsePayload', 'actorEmail', 'statusCode',
            'correlationId', 'createdAt', 'status', 'severity',
        ]

    def get_status(self, obj):
        if obj.status_code is None:
            return ""
        return "SUCCESS" if obj.status_code < 400 else "FAILURE"

    def get_severity(self, obj):
        if obj.status_code and obj.status_code >= 500:
            return "CRITICAL"
        if obj.status_code and obj.status_code >= 400:
            return "WARNING"
        if obj.action in {"LOGIN_FAILED", "KEYCLOAK_LOGIN_FAILED", "MFA_FAILED"}:
            return "WARNING"
        return "INFO"
