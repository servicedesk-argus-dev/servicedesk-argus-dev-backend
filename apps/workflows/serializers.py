from rest_framework import serializers
from .models import Workflow, WorkflowState, WorkflowTransition
from django.contrib.contenttypes.models import ContentType

class WorkflowStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowState
        fields = ['id', 'name', 'is_initial', 'is_final', 'color']

class WorkflowTransitionSerializer(serializers.ModelSerializer):
    from_state_name = serializers.ReadOnlyField(source='from_state.name')
    to_state_name = serializers.ReadOnlyField(source='to_state.name')
    
    class Meta:
        model = WorkflowTransition
        fields = ['id', 'from_state', 'to_state', 'from_state_name', 'to_state_name', 'name', 'required_permission', 'conditions']

class WorkflowSerializer(serializers.ModelSerializer):
    states = WorkflowStateSerializer(many=True, read_only=True)
    transitions = WorkflowTransitionSerializer(many=True, read_only=True)
    target_model = serializers.SerializerMethodField()
    
    class Meta:
        model = Workflow
        fields = ['id', 'name', 'description', 'target_content_type', 'target_model', 'is_active', 'states', 'transitions', 'created_at', 'updated_at']
        
    def get_target_model(self, obj):
        return obj.target_content_type.model
