from rest_framework import serializers
from .models import Incident, WorkNote, Activity, Attachment, IncidentProblem, IncidentChange
from apps.sla.models import TaskSLA
from apps.accounts.serializers import UserSerializer
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer
from apps.sla.serializers import TaskSLASerializer
from apps.sla.services import derive_incident_priority, get_sla_targets, apply_incident_sla_targets
from apps.assignments.validation import validate_assignment_attrs


class IncidentProblemSerializer(serializers.ModelSerializer):
    problem = serializers.SerializerMethodField()

    class Meta:
        model = IncidentProblem
        fields = ['id', 'problem', 'link_type', 'notes']
        read_only_fields = ['id']

    def get_problem(self, obj):
        if obj.problem:
            return {
                'id': str(obj.problem.id),
                'number': obj.problem.number,
                'short_description': obj.problem.short_description,
                'state': obj.problem.state,
            }
        return None


class IncidentChangeSerializer(serializers.ModelSerializer):
    change = serializers.SerializerMethodField()

    class Meta:
        model = IncidentChange
        fields = ['id', 'change', 'notes']
        read_only_fields = ['id']

    def get_change(self, obj):
        if obj.change:
            return {
                'id': str(obj.change.id),
                'number': obj.change.number,
                'short_description': obj.change.short_description,
                'state': obj.change.state,
            }
        return None


class WorkNoteSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = WorkNote
        fields = ['id', 'content', 'is_internal', 'author', 'source', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


class ActivitySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = [
            'id',
            'action',
            'description',
            'old_value',
            'new_value',
            'user',
            'actor_ip',
            'user_agent',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'actor_ip', 'user_agent']


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = Attachment
        fields = ['id', 'filename', 'original_name', 'mime_type', 'size', 'path', 'uploaded_by', 'created_at']
        read_only_fields = ['id', 'uploaded_by', 'created_at']





class ParentIncidentSerializer(serializers.ModelSerializer):
    child_status_summary = serializers.ReadOnlyField()
    hierarchy_level = serializers.ReadOnlyField()
    
    class Meta:
        model = Incident
        fields = ['id', 'number', 'short_description', 'state', 'priority', 'child_status_summary', 'hierarchy_level']


class IncidentSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    assignment_group = serializers.SerializerMethodField()
    config_item = serializers.SerializerMethodField()
    organization = OrganizationSerializer(read_only=True)
    work_notes = WorkNoteSerializer(many=True, read_only=True)
    activities = ActivitySerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    linked_problems = IncidentProblemSerializer(many=True, read_only=True)
    linked_changes = IncidentChangeSerializer(many=True, read_only=True)
    task_slas = TaskSLASerializer(many=True, read_only=True)
    available_transitions = serializers.SerializerMethodField()
    is_assigned_to_me = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    parent = ParentIncidentSerializer(read_only=True)
    child_incidents = ParentIncidentSerializer(many=True, read_only=True)
    child_status_summary = serializers.ReadOnlyField()
    hierarchy_level = serializers.ReadOnlyField()
    root_parent = ParentIncidentSerializer(read_only=True)

    requested_by = UserSerializer(read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'number', 'short_description', 'description', 'state', 
            'impact', 'urgency', 'priority', 'category', 'subcategory', 'site', 'location',
            'assigned_to', 'assignment_group', 'created_by', 'requested_by', 'config_item',
            'parent', 'child_incidents', 'child_status_summary', 'hierarchy_level',
            'root_parent', 'is_major_incident',
            'major_incident_state', 'major_incident_notes',
            'sla_breached', 'response_time', 'resolution_time',
            'sla_target_response', 'sla_target_resolution', 'source',
            'source_alert_id', 'source_alert_name', 'resolved_at', 'closed_at',
            'hold_reason', 'resolution_code', 'resolution_notes', 'organization',
            'work_notes', 'activities', 'attachments', 'linked_problems', 'linked_changes',
            'task_slas', 'available_transitions', 'is_assigned_to_me', 'can_edit',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'created_by', 'created_at', 'updated_at',
            'child_incidents', 'child_status_summary', 'hierarchy_level', 'root_parent'
        ]

    def get_assignment_group(self, obj):
        if obj.assignment_group:
            return {'id': str(obj.assignment_group.id), 'name': obj.assignment_group.name}
        return None

    def get_config_item(self, obj):
        if obj.config_item:
            return {'id': str(obj.config_item.id), 'name': obj.config_item.name}
        return None

    def get_available_transitions(self, obj):
        return IncidentUpdateSerializer.TRANSITIONS.get(obj.state, [])

    def get_is_assigned_to_me(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        from apps.common.permissions import is_assigned_to_service_record
        return is_assigned_to_service_record(request.user, obj)

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        from apps.common.permissions import can_edit_service_record
        return can_edit_service_record(request.user, obj)


class IncidentCreateSerializer(serializers.ModelSerializer):
    organization_id = serializers.PrimaryKeyRelatedField(
        source='organization',
        write_only=True,
        required=False,
        queryset=Organization.objects.filter(is_active=True),
    )

    class Meta:
        model = Incident
        fields = [
            'short_description', 'description', 'impact', 'urgency',
            'category', 'subcategory', 'assigned_to', 'assignment_group',
            'config_item', 'source', 'requested_by', 'site', 'location',
            'parent', 'organization_id'
        ]

    def create(self, validated_data):
        from apps.common.utils import generate_record_number
        from apps.common.permissions import is_service_desk_staff
        
        request = self.context['request']
        explicit_organization = validated_data.pop('organization', None)
        organization = explicit_organization or getattr(request, "organization", None) or request.user.organization
        if organization is None:
            raise serializers.ValidationError({"organization_id": "Client organization is required."})
        if not is_service_desk_staff(request.user) and organization.id != request.user.organization_id:
            raise serializers.ValidationError({"organization_id": "Organization access denied."})
        validate_assignment_attrs(validated_data, organization=organization)
        
        validated_data['number'] = generate_record_number("INC", organization, "last_incident_number")
        validated_data['created_by'] = request.user
        validated_data.setdefault('requested_by', request.user)
        validated_data['organization'] = organization
        impact = validated_data.get("impact", Incident.Impact.TEAM)
        urgency = validated_data.get("urgency", Incident.Urgency.MEDIUM)
        validated_data["priority"] = derive_incident_priority(impact, urgency)
        response_target, resolution_target = get_sla_targets(
            validated_data["organization"],
            validated_data["priority"],
        )
        validated_data["sla_target_response"] = response_target
        validated_data["sla_target_resolution"] = resolution_target

        if not validated_data.get('assignment_group'):
            from django.db.models import Q
            from apps.teams.models import Team

            noc_group = (
                Team.objects.filter(
                    Q(organization=organization) | Q(organization__isnull=True),
                    is_active=True,
                )
                .filter(Q(name__iexact="NOC") | Q(name__icontains="NOC") | Q(name__icontains="L1"))
                .order_by("organization_id", "name")
                .first()
            )
            if noc_group:
                validated_data['assignment_group'] = noc_group
        
        from apps.assignments.services import resolve_assignment
        
        # Only auto-assign if group or user is not manually specified
        if not validated_data.get('assignment_group') or not validated_data.get('assigned_to'):
            # Build temp instance for engine to evaluate
            temp_incident = Incident(**validated_data)
            group, individual = resolve_assignment(temp_incident)
            
            if not validated_data.get('assignment_group') and group:
                validated_data['assignment_group'] = group
            if not validated_data.get('assigned_to') and individual:
                validated_data['assigned_to'] = individual

        return super().create(validated_data)


class IncidentUpdateSerializer(serializers.ModelSerializer):
    TRANSITIONS = {
        Incident.State.NEW: [Incident.State.IN_PROGRESS, Incident.State.ON_HOLD, Incident.State.CANCELLED],
        Incident.State.IN_PROGRESS: [Incident.State.ON_HOLD, Incident.State.ESCALATED, Incident.State.RESOLVED, Incident.State.CANCELLED],
        Incident.State.ON_HOLD: [Incident.State.IN_PROGRESS, Incident.State.ESCALATED, Incident.State.RESOLVED, Incident.State.CANCELLED],
        Incident.State.ESCALATED: [Incident.State.IN_PROGRESS, Incident.State.ON_HOLD, Incident.State.RESOLVED, Incident.State.CANCELLED],
        Incident.State.RESOLVED: [Incident.State.CLOSED, Incident.State.IN_PROGRESS],
        Incident.State.CLOSED: [],  # Terminal — use reopen endpoint
        Incident.State.CANCELLED: [],  # Terminal
    }

    class Meta:
        model = Incident
        fields = [
            'short_description', 'description', 'state', 'impact', 'urgency',
            'priority', 'category', 'subcategory', 'assigned_to',
            'assignment_group', 'hold_reason', 'resolution_code', 'resolution_notes',
            'config_item', 'parent', 'is_major_incident', 'site', 'location',
            'major_incident_state', 'major_incident_notes'
        ]

    def validate_state(self, value):
        instance = self.instance
        if not instance or value == instance.state:
            return value
        allowed = self.TRANSITIONS.get(instance.state, [])
        if value not in allowed:
            raise serializers.ValidationError(
                f"Cannot transition from '{instance.state}' to '{value}'. Allowed: {allowed or ['none']}."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        organization = getattr(instance, "organization", None)
        validate_assignment_attrs(attrs, organization=organization, instance=instance)
        target_state = attrs.get("state", instance.state if instance else Incident.State.NEW)
        resolution_code = attrs.get("resolution_code", instance.resolution_code if instance else None)
        resolution_notes = attrs.get("resolution_notes", instance.resolution_notes if instance else None)
        hold_reason = attrs.get("hold_reason", instance.hold_reason if instance else None)

        if target_state == Incident.State.ON_HOLD and not hold_reason:
            raise serializers.ValidationError({"hold_reason": "Hold reason is required when placing an incident on hold."})
        if target_state in {Incident.State.RESOLVED, Incident.State.CLOSED}:
            if not resolution_code:
                raise serializers.ValidationError({"resolution_code": "Resolution code is required to resolve/close an incident."})
            if not resolution_notes:
                raise serializers.ValidationError({"resolution_notes": "Resolution notes are required to resolve/close an incident."})

        return attrs

    def update(self, instance, validated_data):
        from django.utils import timezone
        priority_was = instance.priority
        impact = validated_data.get("impact", instance.impact)
        urgency = validated_data.get("urgency", instance.urgency)
        if "priority" not in validated_data and ("impact" in validated_data or "urgency" in validated_data):
            validated_data["priority"] = derive_incident_priority(impact, urgency)

        # Auto-stamp lifecycle timestamps
        new_state = validated_data.get("state", instance.state)
        if new_state == Incident.State.RESOLVED and instance.state != Incident.State.RESOLVED:
            validated_data.setdefault("resolved_at", timezone.now())
        if new_state == Incident.State.CLOSED and instance.state != Incident.State.CLOSED:
            validated_data.setdefault("closed_at", timezone.now())
        # Reopening clears resolved/closed timestamps
        if new_state == Incident.State.IN_PROGRESS and instance.state in {Incident.State.RESOLVED, Incident.State.CLOSED}:
            validated_data["resolved_at"] = None
            validated_data["closed_at"] = None

        incident = super().update(instance, validated_data)
        if incident.priority != priority_was or incident.sla_target_response is None or incident.sla_target_resolution is None:
            apply_incident_sla_targets(incident, force=True)
            incident.save(update_fields=["sla_target_response", "sla_target_resolution", "updated_at"])
        return incident
