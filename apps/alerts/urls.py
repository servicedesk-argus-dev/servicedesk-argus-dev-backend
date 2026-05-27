from django.urls import path
from .views import (
    AlertAcknowledgeView,
    AlertCreateIncidentView,
    AlertKnowledgeBaseView,
    AlertListCreateView,
    AlertDetailView,
    AlertSilenceView,
    AlertStatsView,
)

urlpatterns = [
    path("", AlertListCreateView.as_view(), name="alert-list-create"),
    path("kb", AlertKnowledgeBaseView.as_view(), name="alert-kb-no-slash"),
    path("kb/", AlertKnowledgeBaseView.as_view(), name="alert-kb"),
    path("<uuid:pk>/", AlertDetailView.as_view(), name="alert-detail"),
    path("<uuid:pk>/acknowledge", AlertAcknowledgeView.as_view(), name="alert-acknowledge"),
    path("<uuid:pk>/acknowledge/", AlertAcknowledgeView.as_view(), name="alert-acknowledge-slash"),
    path("<uuid:pk>/silence", AlertSilenceView.as_view(), name="alert-silence"),
    path("<uuid:pk>/silence/", AlertSilenceView.as_view(), name="alert-silence-slash"),
    path("<uuid:pk>/create-incident", AlertCreateIncidentView.as_view(), name="alert-create-incident"),
    path("<uuid:pk>/create-incident/", AlertCreateIncidentView.as_view(), name="alert-create-incident-slash"),
    path("stats/", AlertStatsView.as_view(), name="alert-stats"),
]
