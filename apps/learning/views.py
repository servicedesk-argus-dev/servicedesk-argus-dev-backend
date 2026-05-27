from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.audit import create_audit_log
from apps.common.pagination import DefaultPagination
from apps.common.permissions import is_service_desk_staff, user_has_any_permission, user_has_permission
from apps.common.responses import failure, success

from .models import LearningEnrollment, LearningModule, LearningProgress, LearningTrack
from .serializers import (
    LearningAssignSerializer,
    LearningEnrollmentSerializer,
    LearningProgressSerializer,
    LearningProgressUpdateSerializer,
    LearningTrackSerializer,
)


def _ensure_internal(user):
    if not is_service_desk_staff(user):
        raise PermissionDenied("Learning Hub is only available to internal staff.")


def _can_read(user):
    return is_service_desk_staff(user) and user_has_any_permission(user, "learning:read", "learning:complete", "learning:assign", "learning:manage")


def _can_complete(user):
    return is_service_desk_staff(user) and user_has_any_permission(user, "learning:complete", "learning:manage")


def _can_assign(user):
    return is_service_desk_staff(user) and user_has_any_permission(user, "learning:assign", "learning:manage")


def _can_manage(user):
    return is_service_desk_staff(user) and user_has_permission(user, "learning:manage")


class LearningTrackListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination
    queryset = LearningTrack.objects.all()
    serializer_class = LearningTrackSerializer

    def get_queryset(self):
        _ensure_internal(self.request.user)
        queryset = (
            super()
            .get_queryset()
            .select_related("team", "owner", "created_by")
            .prefetch_related("modules")
            .annotate(module_count=Count("modules", distinct=True), enrollment_count=Count("enrollments", distinct=True))
            .order_by("title")
        )
        if self.request.method == "GET" and self.request.query_params.get("includeInactive") not in {"true", "1"}:
            queryset = queryset.filter(is_active=True)

        search = self.request.query_params.get("search", "").strip()
        team_id = self.request.query_params.get("team") or self.request.query_params.get("teamId")
        audience_role = self.request.query_params.get("audienceRole") or self.request.query_params.get("audience_role")
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if team_id:
            queryset = queryset.filter(team_id=team_id)
        if audience_role:
            queryset = queryset.filter(audience_role=audience_role)
        return queryset

    def list(self, request, *args, **kwargs):
        if not _can_read(request.user):
            return failure("You do not have permission to view Learning Hub.", status_code=403)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(LearningTrackSerializer(page, many=True, context={"request": request}).data)
        return success(LearningTrackSerializer(queryset, many=True, context={"request": request}).data)

    def create(self, request, *args, **kwargs):
        if not _can_manage(request.user):
            return failure("Only Learning Hub managers can create KT tracks.", status_code=403)
        serializer = self.get_serializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
            track = serializer.save()
            create_audit_log(request, "LEARNING_TRACK_CREATED", "learning_track", track.id, f"Created KT track {track.title}")
            return success(LearningTrackSerializer(track, context={"request": request}).data, "KT track created.", 201)
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)


class LearningTrackDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]
    queryset = LearningTrack.objects.all()
    serializer_class = LearningTrackSerializer

    def get_queryset(self):
        _ensure_internal(self.request.user)
        return super().get_queryset().select_related("team", "owner", "created_by").prefetch_related("modules")

    def retrieve(self, request, *args, **kwargs):
        if not _can_read(request.user):
            return failure("You do not have permission to view Learning Hub.", status_code=403)
        return success(LearningTrackSerializer(self.get_object(), context={"request": request}).data)

    def partial_update(self, request, *args, **kwargs):
        if not _can_manage(request.user):
            return failure("Only Learning Hub managers can update KT tracks.", status_code=403)
        track = self.get_object()
        serializer = self.get_serializer(track, data=request.data, partial=True, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
            track = serializer.save()
            create_audit_log(request, "LEARNING_TRACK_UPDATED", "learning_track", track.id, f"Updated KT track {track.title}")
            return success(LearningTrackSerializer(track, context={"request": request}).data, "KT track updated.")
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)


class LearningTrackAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        _ensure_internal(request.user)
        if not _can_assign(request.user):
            return failure("Only team leads, NOC, managers, and admins can assign KT tracks.", status_code=403)
        track = LearningTrack.objects.filter(id=pk, is_active=True).first()
        if track is None:
            return failure("KT track not found.", status_code=404)
        serializer = LearningAssignSerializer(data=request.data, context={"request": request, "track": track})
        try:
            serializer.is_valid(raise_exception=True)
            enrollment = serializer.save()
            create_audit_log(
                request,
                "LEARNING_TRACK_ASSIGNED",
                "learning_enrollment",
                enrollment.id,
                f"Assigned {track.title} to {enrollment.user.email}",
            )
            return success(LearningEnrollmentSerializer(enrollment, context={"request": request}).data, "KT track assigned.", 201)
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)


class LearningEnrollmentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination
    serializer_class = LearningEnrollmentSerializer

    def get_queryset(self):
        _ensure_internal(self.request.user)
        queryset = (
            LearningEnrollment.objects.select_related("track", "track__team", "track__owner", "user", "assigned_by", "mentor")
            .prefetch_related("track__modules", "progress")
            .order_by("-created_at")
        )
        if not _can_assign(self.request.user):
            queryset = queryset.filter(user=self.request.user)

        status_value = self.request.query_params.get("status")
        team_id = self.request.query_params.get("team") or self.request.query_params.get("teamId")
        user_id = self.request.query_params.get("user") or self.request.query_params.get("userId")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if team_id:
            queryset = queryset.filter(track__team_id=team_id)
        if user_id and _can_assign(self.request.user):
            queryset = queryset.filter(user_id=user_id)
        return queryset

    def list(self, request, *args, **kwargs):
        if not _can_read(request.user):
            return failure("You do not have permission to view Learning Hub.", status_code=403)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(LearningEnrollmentSerializer(page, many=True, context={"request": request}).data)
        return success(LearningEnrollmentSerializer(queryset, many=True, context={"request": request}).data)


class MyLearningEnrollmentListView(LearningEnrollmentListView):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class LearningProgressUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, module_id):
        _ensure_internal(request.user)
        enrollment = LearningEnrollment.objects.select_related("track", "user").filter(id=pk).first()
        if enrollment is None:
            return failure("Learning enrollment not found.", status_code=404)
        if enrollment.user_id != request.user.id and not _can_assign(request.user):
            return failure("You can only complete your own KT modules.", status_code=403)
        if not _can_complete(request.user) and not _can_assign(request.user):
            return failure("You do not have permission to complete KT modules.", status_code=403)
        module = LearningModule.objects.filter(id=module_id, track=enrollment.track).first()
        if module is None:
            return failure("Learning module not found for this track.", status_code=404)

        serializer = LearningProgressUpdateSerializer(data=request.data, context={"request": request, "enrollment": enrollment, "module": module})
        try:
            serializer.is_valid(raise_exception=True)
            progress = serializer.save()
            create_audit_log(request, "LEARNING_MODULE_COMPLETED", "learning_progress", progress.id, f"Completed KT module {module.title}")
            return success(LearningProgressSerializer(progress, context={"request": request}).data, "KT module completed.")
        except ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)

    def delete(self, request, pk, module_id):
        _ensure_internal(request.user)
        enrollment = LearningEnrollment.objects.select_related("track", "user").filter(id=pk).first()
        if enrollment is None:
            return failure("Learning enrollment not found.", status_code=404)
        if enrollment.user_id != request.user.id and not _can_assign(request.user):
            return failure("You can only update your own KT modules.", status_code=403)
        module = LearningModule.objects.filter(id=module_id, track=enrollment.track).first()
        if module is None:
            return failure("Learning module not found for this track.", status_code=404)
        progress = LearningProgress.objects.filter(enrollment=enrollment, module=module).first()
        if progress:
            progress.completed_at = None
            progress.completed_by = None
            progress.save(update_fields=["completed_at", "completed_by", "updated_at"])
        enrollment.refresh_status()
        create_audit_log(request, "LEARNING_MODULE_REOPENED", "learning_progress", progress.id if progress else None, f"Reopened KT module {module.title}")
        return success({"completed": False}, "KT module marked incomplete.")


class LearningProgressSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_internal(request.user)
        if not _can_assign(request.user):
            return failure("Only team leads, NOC, managers, and admins can view KT progress summary.", status_code=403)
        qs = LearningEnrollment.objects.select_related("track", "track__team", "user").prefetch_related("track__modules", "progress")
        team_id = request.query_params.get("team") or request.query_params.get("teamId")
        if team_id:
            qs = qs.filter(track__team_id=team_id)

        enrollments = list(qs)
        total = len(enrollments)
        completed = sum(1 for item in enrollments if item.status == LearningEnrollment.Status.COMPLETED)
        overdue = sum(1 for item in enrollments if item.is_overdue)
        due_soon = sum(
            1
            for item in enrollments
            if item.due_date
            and item.status != LearningEnrollment.Status.COMPLETED
            and timezone.now() <= item.due_date <= timezone.now() + timedelta(days=7)
        )
        progress_values = [LearningEnrollmentSerializer(item, context={"request": request}).data["progressPercent"] for item in enrollments]
        return success(
            {
                "total": total,
                "assigned": sum(1 for item in enrollments if item.status == LearningEnrollment.Status.ASSIGNED),
                "inProgress": sum(1 for item in enrollments if item.status == LearningEnrollment.Status.IN_PROGRESS),
                "completed": completed,
                "overdue": overdue,
                "dueSoon": due_soon,
                "averageProgress": round(sum(progress_values) / total) if total else 0,
            }
        )
