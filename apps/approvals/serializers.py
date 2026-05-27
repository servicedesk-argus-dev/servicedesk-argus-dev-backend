from rest_framework import serializers
from .models import ApprovalRequest, Approver
from apps.accounts.serializers import UserSerializer

class ApproverSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Approver
        fields = ['id', 'user', 'user_details', 'state', 'comments', 'actioned_at']
        read_only_fields = ['id', 'state', 'actioned_at']

class ApprovalRequestSerializer(serializers.ModelSerializer):
    approvers = ApproverSerializer(many=True, read_only=True)
    target_object_details = serializers.SerializerMethodField()
    
    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'title', 'description', 'state', 'approvers', 
            'target_object_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'state', 'created_at', 'updated_at']
        
    def get_target_object_details(self, obj):
        if hasattr(obj.content_object, 'number'):
            return {"number": obj.content_object.number, "type": obj.content_type.model}
        return {"id": str(obj.object_id), "type": obj.content_type.model}
