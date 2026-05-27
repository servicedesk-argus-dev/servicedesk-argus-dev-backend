import json

from rest_framework import serializers
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer
from .models import Integration

class IntegrationSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        queryset=Organization.objects.all(),
        write_only=True,
        required=False,
    )
    status = serializers.SerializerMethodField()
    last_sync_at = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Integration
        fields = (
            "id",
            "organization",
            "organization_id",
            "name",
            "type",
            "config",
            "is_active",
            "status",
            "last_sync_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "status", "last_sync_at", "created_at", "updated_at")

    def get_status(self, obj):
        return "ACTIVE" if obj.is_active else "INACTIVE"

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        status = mutable.pop("status", None)
        if status is not None and "is_active" not in mutable:
            mutable["is_active"] = str(status).upper() == "ACTIVE"

        config = mutable.get("config")
        if isinstance(config, str):
            try:
                mutable["config"] = json.loads(config) if config else {}
            except json.JSONDecodeError:
                mutable["config"] = {"raw": config}

        return super().to_internal_value(mutable)
