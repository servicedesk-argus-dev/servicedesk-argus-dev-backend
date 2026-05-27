from django.urls import path

from .views import (
    LearningEnrollmentListView,
    LearningProgressSummaryView,
    LearningProgressUpdateView,
    LearningTrackAssignView,
    LearningTrackDetailView,
    LearningTrackListCreateView,
    MyLearningEnrollmentListView,
)


urlpatterns = [
    path("tracks/", LearningTrackListCreateView.as_view(), name="learning-track-list"),
    path("tracks/<uuid:pk>/", LearningTrackDetailView.as_view(), name="learning-track-detail"),
    path("tracks/<uuid:pk>/assign/", LearningTrackAssignView.as_view(), name="learning-track-assign"),
    path("enrollments/", LearningEnrollmentListView.as_view(), name="learning-enrollment-list"),
    path("my-tracks/", MyLearningEnrollmentListView.as_view(), name="learning-my-tracks"),
    path("enrollments/<uuid:pk>/modules/<uuid:module_id>/complete/", LearningProgressUpdateView.as_view(), name="learning-module-complete"),
    path("progress-summary/", LearningProgressSummaryView.as_view(), name="learning-progress-summary"),
]
