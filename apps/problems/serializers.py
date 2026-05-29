"""
Problem serializers — read / create / update / nested helpers.

Naming convention mirrors the incidents app:
  - ProblemSerializer        → full read (list + detail)
  - ProblemCreateSerializer  → POST /problems/
  - ProblemUpdateSerializer  → PATCH /problems/<id>/
  - WorkNoteSerializer       → POST /problems/<id>/notes/
  - LinkedIncidentSerializer → nested inside ProblemSerializer
"""

from __future__ import annotations

import random
import string

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.changes.models import Change
from apps.accounts.serializers import UserSerializer
from apps.assignments.validation import validate_assignment_attrs
from apps.incidents.models import Activity
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer
from apps.teams.models import Team

from .models import Problem, ProblemTask

User = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_problem_number() -> str:
    """PRB + 4-digit year + 6 random digits, e.g. PRB20260012345."""
    suffix = "".join(random.choices(string.digits, k=6))
    return f"PRB{timezone.now().year}{suffix}"


def _generate_known_error_id() -> str:
    suffix = "".join(random.choices(string.digits, k=6))
    return f"KE{timezone.now().year}{suffix}"


# ─── Nested serializers ───────────────────────────────────────────────────────

class LinkedIncidentSerializer(serializers.Serializer):
    """
    Lightweight read-only view of an IncidentProblem link.
    Avoids a circular import by not importing IncidentSerializer.
    """

    id = serializers.UUIDField(source="incident.id")
    number = serializers.CharField(source="incident.number")
    short_description = serializers.CharField(source="incident.short_description")
    state = serializers.CharField(source="incident.state")
    priority = serializers.CharField(source="incident.priority")
    alert_name = serializers.CharField(
        source="incident.source_alert_name", default=None
    )
    link_type = serializers.CharField()
    notes = serializers.CharField(default=None)


class WorkNoteReadSerializer(serializers.Serializer):
    """Read-only work note shape returned inside problem detail."""

    id = serializers.UUIDField()
    content = serializers.CharField()
    is_internal = serializers.BooleanField()
    author = UserSerializer()
    source = serializers.CharField()
    created_at = serializers.DateTimeField()


class ActivityReadSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "action", "description", "old_value", "new_value", "user", "created_at"]


class ProblemTaskSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(read_only=True)
    assignment_group = serializers.SerializerMethodField()

    class Meta:
        model = ProblemTask
        fields = [
            'id', 'number', 'short_description', 'description', 'state',
            'priority', 'assigned_to', 'assignment_group', 'due_date',
            'completed_at', 'created_at', 'updated_at'
        ]

    def get_assignment_group(self, obj):
        if obj.assignment_group:
            return {'id': str(obj.assignment_group.id), 'name': obj.assignment_group.name}
        return None


# ─── Main serializers ─────────────────────────────────────────────────────────

class ProblemSerializer(serializers.ModelSerializer):
    """Full read serializer — used for list and detail responses."""

    assigned_to = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)

    # Computed / nested
    assignment_group = serializers.SerializerMethodField()
    related_change_info = serializers.SerializerMethodField()
    linked_incidents = LinkedIncidentSerializer(many=True, read_only=True)
    work_notes = WorkNoteReadSerializer(many=True, read_only=True)
    activities = ActivityReadSerializer(many=True, read_only=True)
    tasks = ProblemTaskSerializer(many=True, read_only=True)
    available_transitions = serializers.SerializerMethodField()
    is_assigned_to_me = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = [
            "id",
            "number",
            "short_description",
            "description",
            "state",
            "priority",
            "category",
            # assignment
            "assigned_to",
            "assignment_group",
            "created_by",
            # RCA fields
            "root_cause",
            "root_cause_analysis",
            "workaround",
            "workaround_effective",
            "permanent_fix",
            "fix_implemented",
            # relations
            "related_change",
            "related_change_info",
            "is_known_error",
            "known_error_id",
            "available_transitions",
            "is_assigned_to_me",
            "can_edit",
            # nested
            "linked_incidents",
            "work_notes",
            "activities",
            "tasks",
            # meta
            "organization",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "number", "created_by", "created_at", "updated_at", "tasks"]

    def get_assignment_group(self, obj: Problem) -> dict | None:
        if obj.assignment_group_id:
            return {
                "id": str(obj.assignment_group.id),
                "name": obj.assignment_group.name,
            }
        return None

    def get_related_change_info(self, obj: Problem) -> dict | None:
        if obj.related_change_id:
            return {
                "id": str(obj.related_change.id),
                "number": obj.related_change.number,
                "short_description": obj.related_change.short_description,
            }
        return None

    def get_available_transitions(self, obj: Problem) -> list[str]:
        transitions: dict[str, list[str]] = {
            Problem.State.NEW: [Problem.State.INVESTIGATION],
            Problem.State.INVESTIGATION: [
                Problem.State.RCA_IN_PROGRESS,
                Problem.State.KNOWN_ERROR,
            ],
            Problem.State.RCA_IN_PROGRESS: [
                Problem.State.KNOWN_ERROR,
                Problem.State.RESOLVED,
            ],
            Problem.State.KNOWN_ERROR: [Problem.State.RESOLVED],
            Problem.State.RESOLVED: [Problem.State.CLOSED, Problem.State.INVESTIGATION],
            Problem.State.CLOSED: [Problem.State.INVESTIGATION],
        }
        return transitions.get(obj.state, [])

    def get_is_assigned_to_me(self, obj: Problem) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        from apps.common.permissions import is_assigned_to_service_record
        return is_assigned_to_service_record(request.user, obj)

    def get_can_edit(self, obj: Problem) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        from apps.common.permissions import can_edit_service_record
        return can_edit_service_record(request.user, obj)


class ProblemCreateSerializer(serializers.ModelSerializer):
    """
    POST /problems/
    Accepts camelCase aliases via source= so the frontend payload works
    without transformation.
    """

    # Accept both snake_case (API clients) and camelCase (frontend)
    assignment_group = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(), required=False, allow_null=True
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    related_change = serializers.PrimaryKeyRelatedField(
        queryset=Change.objects.all(), required=False, allow_null=True
    )
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        write_only=True,
        required=False,
        queryset=Organization.objects.filter(is_active=True),
    )

    class Meta:
        model = Problem
        fields = [
            "short_description",
            "description",
            "priority",
            "category",
            "assigned_to",
            "assignment_group",
            "related_change",
            "root_cause",
            "workaround",
            "permanent_fix",
            "organization_id",
        ]

    def validate_short_description(self, value: str) -> str:
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Short description must be at least 3 characters."
            )
        return value.strip()

    def validate(self, attrs: dict) -> dict:
        request = self.context["request"]
        from apps.common.permissions import is_service_desk_staff

        organization = attrs.get("organization") or getattr(request, "organization", None) or getattr(request.user, "organization", None)
        if organization is None:
            return attrs
        if not is_service_desk_staff(request.user) and organization.id != request.user.organization_id:
            raise serializers.ValidationError({"organization_id": "Organization access denied."})

        related_change = attrs.get("related_change")

        validate_assignment_attrs(attrs, organization=organization)
        if related_change and related_change.organization_id != organization.id:
            raise serializers.ValidationError(
                {"related_change": "Selected change does not belong to your organisation."}
            )
        return attrs

    def create(self, validated_data: dict) -> Problem:
        request = self.context["request"]
        org = validated_data.pop("organization", None) or getattr(request, "organization", None) or getattr(request.user, "organization", None)

        if org is None:
            raise serializers.ValidationError(
                "User must belong to an organisation to create a problem."
            )

        validated_data["number"] = _generate_problem_number()
        validated_data["created_by"] = request.user
        validated_data["organization"] = org
        return super().create(validated_data)


class ProblemUpdateSerializer(serializers.ModelSerializer):
    """
    PATCH /problems/<id>/
    All fields optional; frontend sends camelCase which DRF maps via source=.
    """

    assignment_group = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(), required=False, allow_null=True
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Problem
        fields = [
            "short_description",
            "description",
            "state",
            "priority",
            "category",
            "assigned_to",
            "assignment_group",
            "root_cause",
            "root_cause_analysis",
            "workaround",
            "workaround_effective",
            "permanent_fix",
            "fix_implemented",
            "is_known_error",
            "known_error_id",
        ]

    def validate_state(self, value: str) -> str:
        """Enforce allowed state transitions."""
        instance = self.instance
        if instance is None:
            return value

        transitions: dict[str, list[str]] = {
            Problem.State.NEW: [Problem.State.INVESTIGATION],
            Problem.State.INVESTIGATION: [
                Problem.State.RCA_IN_PROGRESS,
                Problem.State.KNOWN_ERROR,
            ],
            Problem.State.RCA_IN_PROGRESS: [
                Problem.State.KNOWN_ERROR,
                Problem.State.RESOLVED,
            ],
            Problem.State.KNOWN_ERROR: [Problem.State.RESOLVED],
            Problem.State.RESOLVED: [Problem.State.CLOSED, Problem.State.INVESTIGATION],
            Problem.State.CLOSED: [Problem.State.INVESTIGATION],
        }

        allowed = transitions.get(instance.state, [])
        if value != instance.state and value not in allowed:
            raise serializers.ValidationError(
                f"Cannot transition from '{instance.state}' to '{value}'. "
                f"Allowed: {allowed or ['none']}."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        organization = getattr(self.instance, "organization", None)
        validate_assignment_attrs(attrs, organization=organization, instance=self.instance)
        return attrs

    def update(self, instance: Problem, validated_data: dict) -> Problem:
        target_state = validated_data.get("state", instance.state)
        target_known_error = validated_data.get("is_known_error", instance.is_known_error)
        if (target_state == Problem.State.KNOWN_ERROR or target_known_error) and not instance.known_error_id and not validated_data.get("known_error_id"):
            validated_data["is_known_error"] = True
            validated_data["known_error_id"] = _generate_known_error_id()
        return super().update(instance, validated_data)


class WorkNoteCreateSerializer(serializers.Serializer):
    """POST /problems/<id>/notes/"""

    content = serializers.CharField(min_length=1)
    is_internal = serializers.BooleanField(default=False)

    def validate_content(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Work note content cannot be empty.")
        return value
