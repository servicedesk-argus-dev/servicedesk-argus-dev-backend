from rest_framework import serializers
from .models import Change, Approval, ChangeCI
from apps.accounts.serializers import UserSerializer
from apps.assignments.validation import validate_assignment_attrs
from apps.organizations.serializers import OrganizationSerializer
from apps.incidents.models import Activity, WorkNote


class ApprovalSerializer(serializers.ModelSerializer):
    approver = UserSerializer(read_only=True)

    class Meta:
        model = Approval
        fields = ['id', 'approver', 'state', 'comments', 'approved_at', 'created_at']
        read_only_fields = ['id', 'approver', 'created_at']


class ChangeCISerializer(serializers.ModelSerializer):
    config_item = serializers.SerializerMethodField()

    class Meta:
        model = ChangeCI
        fields = ['id', 'config_item', 'impact_type']
        read_only_fields = ['id']

    def get_config_item(self, obj):
        if obj.config_item:
            return {'id': str(obj.config_item.id), 'name': obj.config_item.name}
        return None


class ChangeWorkNoteSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = WorkNote
        fields = ['id', 'content', 'is_internal', 'author', 'source', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


class ChangeActivitySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'action', 'description', 'old_value', 'new_value', 'user', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class ChangeLinkedIncidentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    link_type = serializers.CharField(default="RELATED_CHANGE")
    notes = serializers.CharField(default=None)
    incident = serializers.SerializerMethodField()

    def get_incident(self, obj):
        if obj.incident:
            return {
                'id': str(obj.incident.id),
                'number': obj.incident.number,
                'short_description': obj.incident.short_description,
                'state': obj.incident.state,
                'priority': obj.incident.priority,
            }
        return None


class ChangeSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    assignment_group = serializers.SerializerMethodField()
    organization = OrganizationSerializer(read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    affected_cis = ChangeCISerializer(many=True, read_only=True)
    linked_incidents = ChangeLinkedIncidentSerializer(many=True, read_only=True)
    work_notes = ChangeWorkNoteSerializer(many=True, read_only=True)
    activities = ChangeActivitySerializer(many=True, read_only=True)
    available_transitions = serializers.SerializerMethodField()
    required_fields_for_state = serializers.SerializerMethodField()
    is_assigned_to_me = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Change
        fields = [
            'id', 'number', 'short_description', 'description', 'type', 'state',
            'risk_level', 'category', 'assigned_to', 'assignment_group', 'created_by',
            'justification', 'implementation_plan', 'rollback_plan', 'test_plan',
            'communication_plan', 'planned_start_date', 'planned_end_date',
            'actual_start_date', 'actual_end_date', 'affected_services', 'downtime',
            'user_impact', 'git_repo_url', 'git_branch', 'git_commit_hash',
            'pull_request_url', 'review_notes', 'closure_code', 'organization',
            'approvals', 'affected_cis', 'linked_incidents', 'work_notes',
            'activities', 'available_transitions', 'required_fields_for_state',
            'is_assigned_to_me', 'can_edit', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'number', 'created_by', 'created_at', 'updated_at']

    def get_assignment_group(self, obj):
        if obj.assignment_group:
            return {'id': str(obj.assignment_group.id), 'name': obj.assignment_group.name}
        return None

    def get_available_transitions(self, obj):
        transitions = ChangeUpdateSerializer.TYPE_TRANSITIONS.get(obj.type, ChangeUpdateSerializer.TYPE_TRANSITIONS[Change.Type.NORMAL])
        return transitions.get(obj.state, [])

    def get_required_fields_for_state(self, _obj):
        return {
            Change.State.APPROVAL: ["implementation_plan", "rollback_plan", "test_plan"],
            Change.State.SCHEDULED: ["implementation_plan", "rollback_plan", "test_plan"],
            Change.State.IMPLEMENTING: ["implementation_plan", "rollback_plan", "test_plan"],
            Change.State.CLOSED: ["review_notes", "closure_code"],
        }

    def get_is_assigned_to_me(self, obj):
        request = self.context.get('request')
        if request is None:
            return False
        from apps.common.permissions import is_assigned_to_service_record
        return is_assigned_to_service_record(request.user, obj)

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request is None:
            return False
        from apps.common.permissions import can_edit_service_record
        return can_edit_service_record(request.user, obj)


class ChangeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Change
        fields = [
            'short_description', 'description', 'type', 'risk_level', 'category',
            'assigned_to', 'assignment_group', 'justification', 'implementation_plan',
            'rollback_plan', 'test_plan', 'communication_plan', 'planned_start_date',
            'planned_end_date', 'affected_services', 'downtime', 'user_impact',
            'git_repo_url', 'git_branch', 'git_commit_hash', 'pull_request_url'
        ]

    def create(self, validated_data):
        from apps.common.utils import generate_record_number

        request = self.context['request']
        organization = getattr(request, "organization", None) or getattr(request.user, "organization", None)
        if organization is None:
            raise serializers.ValidationError("User must belong to an organisation to create a change.")
        validate_assignment_attrs(validated_data, organization=organization)
        validated_data['number'] = generate_record_number("CHG", organization, "last_change_number")
        validated_data['created_by'] = request.user
        validated_data['organization'] = organization

        # Emergency changes skip straight to IMPLEMENTING
        if validated_data.get('type') == Change.Type.EMERGENCY:
            validated_data.setdefault('state', Change.State.IMPLEMENTING)

        return super().create(validated_data)


class ChangeUpdateSerializer(serializers.ModelSerializer):
    TYPE_TRANSITIONS = {
        Change.Type.NORMAL: {
            Change.State.NEW: [Change.State.ASSESSMENT, Change.State.CANCELLED],
            Change.State.ASSESSMENT: [Change.State.APPROVAL, Change.State.CANCELLED],
            Change.State.APPROVAL: [Change.State.SCHEDULED, Change.State.CANCELLED],
            Change.State.SCHEDULED: [Change.State.IMPLEMENTING, Change.State.CANCELLED],
            Change.State.IMPLEMENTING: [Change.State.REVIEW, Change.State.CANCELLED],
            Change.State.REVIEW: [Change.State.CLOSED, Change.State.CANCELLED],
            Change.State.CLOSED: [],
            Change.State.CANCELLED: [],
        },
        Change.Type.STANDARD: {
            Change.State.NEW: [Change.State.ASSESSMENT, Change.State.SCHEDULED, Change.State.CANCELLED],
            Change.State.ASSESSMENT: [Change.State.SCHEDULED, Change.State.CANCELLED],
            Change.State.APPROVAL: [Change.State.SCHEDULED, Change.State.CANCELLED],
            Change.State.SCHEDULED: [Change.State.IMPLEMENTING, Change.State.CANCELLED],
            Change.State.IMPLEMENTING: [Change.State.REVIEW, Change.State.CANCELLED],
            Change.State.REVIEW: [Change.State.CLOSED, Change.State.CANCELLED],
            Change.State.CLOSED: [],
            Change.State.CANCELLED: [],
        },
        Change.Type.EMERGENCY: {
            Change.State.NEW: [Change.State.APPROVAL, Change.State.IMPLEMENTING, Change.State.CANCELLED],
            Change.State.ASSESSMENT: [Change.State.APPROVAL, Change.State.IMPLEMENTING, Change.State.CANCELLED],
            Change.State.APPROVAL: [Change.State.IMPLEMENTING, Change.State.CANCELLED],
            Change.State.SCHEDULED: [Change.State.IMPLEMENTING, Change.State.CANCELLED],
            Change.State.IMPLEMENTING: [Change.State.REVIEW, Change.State.CANCELLED],
            Change.State.REVIEW: [Change.State.CLOSED, Change.State.CANCELLED],
            Change.State.CLOSED: [],
            Change.State.CANCELLED: [],
        },
    }

    class Meta:
        model = Change
        fields = [
            'short_description', 'description', 'type', 'state', 'risk_level', 'category',
            'assigned_to', 'assignment_group', 'justification', 'implementation_plan',
            'rollback_plan', 'test_plan', 'communication_plan', 'planned_start_date',
            'planned_end_date', 'actual_start_date', 'actual_end_date',
            'affected_services', 'downtime', 'user_impact', 'git_repo_url',
            'git_branch', 'git_commit_hash', 'pull_request_url', 'review_notes',
            'closure_code'
        ]

    def validate_state(self, value):
        instance = self.instance
        if not instance or value == instance.state:
            return value
        transitions = self.TYPE_TRANSITIONS.get(instance.type, self.TYPE_TRANSITIONS[Change.Type.NORMAL])
        allowed = transitions.get(instance.state, [])
        if value not in allowed:
            raise serializers.ValidationError(
                f"Cannot transition from '{instance.state}' to '{value}' for change type '{instance.type}'. "
                f"Allowed: {allowed or ['none']}."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        organization = getattr(instance, "organization", None)
        validate_assignment_attrs(attrs, organization=organization, instance=instance)
        target_state = attrs.get("state", instance.state if instance else Change.State.NEW)

        implementation_plan = attrs.get("implementation_plan", instance.implementation_plan if instance else None)
        rollback_plan = attrs.get("rollback_plan", instance.rollback_plan if instance else None)
        test_plan = attrs.get("test_plan", instance.test_plan if instance else None)
        review_notes = attrs.get("review_notes", instance.review_notes if instance else None)
        closure_code = attrs.get("closure_code", instance.closure_code if instance else None)

        if target_state in {Change.State.APPROVAL, Change.State.SCHEDULED, Change.State.IMPLEMENTING}:
            if not implementation_plan:
                raise serializers.ValidationError({"implementation_plan": "Implementation plan is required before approval/schedule/implementation."})
            if not rollback_plan:
                raise serializers.ValidationError({"rollback_plan": "Rollback plan is required before approval/schedule/implementation."})
            if not test_plan:
                raise serializers.ValidationError({"test_plan": "Test plan is required before approval/schedule/implementation."})

        if target_state == Change.State.CLOSED:
            if not review_notes:
                raise serializers.ValidationError({"review_notes": "Review notes are required before closing a change."})
            if not closure_code:
                raise serializers.ValidationError({"closure_code": "Closure code is required before closing a change."})

        return attrs
