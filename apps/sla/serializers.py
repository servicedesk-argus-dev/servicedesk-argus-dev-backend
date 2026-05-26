from rest_framework import serializers

from .models import SLADefinition, TaskSLA


class SLADefinitionSerializer(serializers.ModelSerializer):
    appliesTo = serializers.CharField(source="applies_to", read_only=True)
    responseTimeMinutes = serializers.IntegerField(source="response_time_minutes")
    resolutionTimeMinutes = serializers.IntegerField(source="resolution_time_minutes")
    businessHoursOnly = serializers.BooleanField(source="business_hours_only")
    isActive = serializers.BooleanField(source="is_active")
    startCondition = serializers.JSONField(source="start_condition", read_only=True)
    pauseCondition = serializers.JSONField(source="pause_condition", read_only=True)
    stopCondition = serializers.JSONField(source="stop_condition", read_only=True)
    resetCondition = serializers.JSONField(source="reset_condition", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SLADefinition
        fields = [
            "id",
            "name",
            "appliesTo",
            "priority",
            "responseTimeMinutes",
            "resolutionTimeMinutes",
            "businessHoursOnly",
            "isActive",
            "startCondition",
            "pauseCondition",
            "stopCondition",
            "resetCondition",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "priority"]

    def validate_responseTimeMinutes(self, value):
        if value < 1:
            raise serializers.ValidationError("Response target must be at least 1 minute.")
        return value

    def validate_resolutionTimeMinutes(self, value):
        if value < 1:
            raise serializers.ValidationError("Resolution target must be at least 1 minute.")
        return value


class TaskSLASerializer(serializers.ModelSerializer):
    sla_name = serializers.CharField(source='sla_definition.name', read_only=True)
    totalPauseDuration = serializers.DurationField(source='total_pause_duration', read_only=True)
    businessElapsedTime = serializers.DurationField(source='business_elapsed_time', read_only=True)
    percentageElapsed = serializers.FloatField(source='percentage_elapsed', read_only=True)
    hasBreached = serializers.BooleanField(source='has_breached', read_only=True)
    startTime = serializers.DateTimeField(source='start_time', read_only=True)
    pauseTime = serializers.DateTimeField(source='pause_time', read_only=True)
    stopTime = serializers.DateTimeField(source='stop_time', read_only=True)

    class Meta:
        model = TaskSLA
        fields = [
            'id', 'sla_name', 'stage', 'startTime', 'pauseTime', 'stopTime',
            'totalPauseDuration', 'businessElapsedTime', 'percentageElapsed',
            'hasBreached'
        ]
        read_only_fields = fields

