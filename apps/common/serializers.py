from rest_framework import serializers
from .models import AuditLog
from apps.accounts.serializers import UserSerializer

class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'action', 'resource_type', 'resource_id', 
            'description', 'ip_address', 'user_agent', 
            'request_payload', 'response_payload', 'created_at', 'user'
        ]
