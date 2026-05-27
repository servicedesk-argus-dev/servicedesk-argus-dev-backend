from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.common.permissions import is_service_desk_staff
from apps.teams.models import Team
from apps.teams.serializers import TeamSerializer

from .models import LearningEnrollment, LearningModule, LearningProgress, LearningTrack

User = get_user_model()


class LearningModuleSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    moduleType = serializers.CharField(source="module_type", read_only=True)
    module_type = serializers.ChoiceField(choices=LearningModule.ModuleType.choices, required=False)
    externalUrl = serializers.URLField(source="external_url", read_only=True)
    estimatedMinutes = serializers.IntegerField(source="estimated_minutes", read_only=True)
    isRequired = serializers.BooleanField(source="is_required", read_only=True)
    isCompleted = serializers.SerializerMethodField()
    completedAt = serializers.SerializerMethodField()

    class Meta:
        model = LearningModule
        fields = [
            "id",
            "order",
            "title",
            "module_type",
            "moduleType",
            "content",
            "external_url",
            "externalUrl",
            "estimated_minutes",
            "estimatedMinutes",
            "is_required",
            "isRequired",
            "isCompleted",
            "completedAt",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_isCompleted(self, obj):
        progress_by_module = self.context.get("progress_by_module") or {}
        return bool(progress_by_module.get(str(obj.id)))

    def get_completedAt(self, obj):
        progress_by_module = self.context.get("progress_by_module") or {}
        progress = progress_by_module.get(str(obj.id))
        return progress.completed_at if progress else None


class LearningTrackSerializer(serializers.ModelSerializer):
    audienceRole = serializers.CharField(source="audience_role", read_only=True)
    audience_role = serializers.ChoiceField(choices=LearningTrack.AudienceRole.choices, required=False)
    team = TeamSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(source="team", queryset=Team.objects.all(), write_only=True, required=False, allow_null=True)
    owner = UserSerializer(read_only=True)
    owner_id = serializers.PrimaryKeyRelatedField(source="owner", queryset=User.objects.all(), write_only=True, required=False, allow_null=True)
    createdBy = UserSerializer(source="created_by", read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    modules = LearningModuleSerializer(many=True, required=False)
    moduleCount = serializers.SerializerMethodField()
    enrollmentCount = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = LearningTrack
        fields = [
            "id",
            "title",
            "audience_role",
            "audienceRole",
            "description",
            "team",
            "team_id",
            "owner",
            "owner_id",
            "is_active",
            "isActive",
            "modules",
            "moduleCount",
            "enrollmentCount",
            "created_by",
            "createdBy",
            "created_at",
            "createdAt",
            "updated_at",
            "updatedAt",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_moduleCount(self, obj):
        return getattr(obj, "module_count", None) or obj.modules.count()

    def get_enrollmentCount(self, obj):
        return getattr(obj, "enrollment_count", None) or obj.enrollments.count()

    def validate_owner_id(self, owner):
        if owner and not is_service_desk_staff(owner):
            raise serializers.ValidationError("Track owner must be an internal staff user.")
        return owner

    def _sync_modules(self, track, modules_data):
        if modules_data is None:
            return
        modules_data = [dict(module_data) for module_data in modules_data]
        existing = {str(module.id): module for module in track.modules.all()}
        incoming_existing_ids = {
            str(module_data.get("id"))
            for module_data in modules_data
            if module_data.get("id") and str(module_data.get("id")) in existing
        }
        if incoming_existing_ids or modules_data == []:
            track.modules.exclude(id__in=incoming_existing_ids).delete()
        for offset, module_id in enumerate(incoming_existing_ids, start=1):
            module = existing[module_id]
            module.order = 100000 + offset
            module.save(update_fields=["order", "updated_at"])

        seen_ids = set()
        for index, module_data in enumerate(modules_data, start=1):
            module_id = str(module_data.pop("id", "") or "")
            module_data.setdefault("order", index)
            if module_id and module_id in existing:
                module = existing[module_id]
                seen_ids.add(module_id)
                for field, value in module_data.items():
                    setattr(module, field, value)
                module.save()
            else:
                LearningModule.objects.create(track=track, **module_data)

    @transaction.atomic
    def create(self, validated_data):
        modules_data = validated_data.pop("modules", None)
        request = self.context.get("request")
        if request and not validated_data.get("owner"):
            validated_data["owner"] = request.user
        if request:
            validated_data["created_by"] = request.user
        track = LearningTrack.objects.create(**validated_data)
        self._sync_modules(track, modules_data)
        return track

    @transaction.atomic
    def update(self, instance, validated_data):
        modules_data = validated_data.pop("modules", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._sync_modules(instance, modules_data)
        return instance


class LearningProgressSerializer(serializers.ModelSerializer):
    module = LearningModuleSerializer(read_only=True)
    completedBy = UserSerializer(source="completed_by", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    isCompleted = serializers.BooleanField(source="is_completed", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = LearningProgress
        fields = [
            "id",
            "module",
            "completed_by",
            "completedBy",
            "completed_at",
            "completedAt",
            "isCompleted",
            "notes",
            "created_at",
            "createdAt",
            "updated_at",
            "updatedAt",
        ]


class LearningEnrollmentSerializer(serializers.ModelSerializer):
    track = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all(), write_only=True, required=False)
    assignedBy = UserSerializer(source="assigned_by", read_only=True)
    mentor = UserSerializer(read_only=True)
    mentor_id = serializers.PrimaryKeyRelatedField(source="mentor", queryset=User.objects.all(), write_only=True, required=False, allow_null=True)
    dueDate = serializers.DateTimeField(source="due_date", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    isOverdue = serializers.BooleanField(source="is_overdue", read_only=True)
    progressPercent = serializers.SerializerMethodField()
    completedModules = serializers.SerializerMethodField()
    totalModules = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = LearningEnrollment
        fields = [
            "id",
            "track",
            "user",
            "user_id",
            "assigned_by",
            "assignedBy",
            "mentor",
            "mentor_id",
            "due_date",
            "dueDate",
            "status",
            "completed_at",
            "completedAt",
            "isOverdue",
            "progressPercent",
            "completedModules",
            "totalModules",
            "created_at",
            "createdAt",
            "updated_at",
            "updatedAt",
        ]
        read_only_fields = ["assigned_by", "status", "completed_at", "created_at", "updated_at"]

    def get_track(self, obj):
        progress_by_module = {
            str(progress.module_id): progress
            for progress in obj.progress.filter(completed_at__isnull=False)
        }
        return LearningTrackSerializer(obj.track, context={**self.context, "progress_by_module": progress_by_module}).data

    def get_totalModules(self, obj):
        return obj.track.modules.filter(is_required=True).count() or obj.track.modules.count()

    def get_completedModules(self, obj):
        if obj.track.modules.filter(is_required=True).exists():
            return obj.progress.filter(module__is_required=True, completed_at__isnull=False).count()
        return obj.progress.filter(completed_at__isnull=False).count()

    def get_progressPercent(self, obj):
        total = self.get_totalModules(obj)
        if not total:
            return 0
        return round((self.get_completedModules(obj) / total) * 100)

    def validate_user_id(self, user):
        if not is_service_desk_staff(user):
            raise serializers.ValidationError("Learning tracks can only be assigned to internal staff.")
        return user

    def validate_mentor_id(self, mentor):
        if mentor and not is_service_desk_staff(mentor):
            raise serializers.ValidationError("Mentor must be an internal staff user.")
        return mentor


class LearningAssignSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all())
    mentor_id = serializers.PrimaryKeyRelatedField(source="mentor", queryset=User.objects.all(), required=False, allow_null=True)
    due_date = serializers.DateTimeField(required=False, allow_null=True)

    def validate_user_id(self, user):
        if not is_service_desk_staff(user):
            raise serializers.ValidationError("Learning tracks can only be assigned to internal staff.")
        return user

    def validate_mentor_id(self, mentor):
        if mentor and not is_service_desk_staff(mentor):
            raise serializers.ValidationError("Mentor must be an internal staff user.")
        return mentor

    def create(self, validated_data):
        track = self.context["track"]
        request = self.context["request"]
        enrollment, _created = LearningEnrollment.objects.update_or_create(
            track=track,
            user=validated_data["user"],
            defaults={
                "mentor": validated_data.get("mentor"),
                "due_date": validated_data.get("due_date"),
                "assigned_by": request.user,
            },
        )
        return enrollment


class LearningProgressUpdateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        enrollment = self.context["enrollment"]
        module = self.context["module"]
        user = self.context["request"].user
        progress, _created = LearningProgress.objects.get_or_create(enrollment=enrollment, module=module)
        progress.completed_at = timezone.now()
        progress.completed_by = user
        progress.notes = self.validated_data.get("notes", progress.notes)
        progress.save()
        enrollment.refresh_status()
        return progress
