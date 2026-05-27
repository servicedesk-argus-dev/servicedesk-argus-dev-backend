"""
Problem URL routing.

Endpoints:
  GET    /problems/                  → list
  POST   /problems/                  → create
  GET    /problems/stats/            → stats + KEDB
  GET    /problems/<uuid>/           → detail
  PATCH  /problems/<uuid>/           → update
  POST   /problems/<uuid>/notes/     → add work note
  POST   /problems/<uuid>/ai-rca/    → trigger AI RCA
  PATCH  /problems/<uuid>/rca/       → apply RCA fields
"""

from django.urls import path

from .views import (
    ProblemAiRcaView,
    ProblemChangeLinkView,
    ProblemDetailView,
    ProblemIncidentLinkView,
    ProblemListCreateView,
    ProblemRcaPatchView,
    ProblemStatsView,
    ProblemWorkNoteView,
)

urlpatterns = [
    # List + Create
    path("", ProblemListCreateView.as_view(), name="problem-list-create"),
    # Stats (must come before <uuid> to avoid route collision)
    path("stats/", ProblemStatsView.as_view(), name="problem-stats"),
    # Detail + Update
    path("<uuid:pk>/", ProblemDetailView.as_view(), name="problem-detail"),
    # Work Notes
    path("<uuid:pk>/notes/", ProblemWorkNoteView.as_view(), name="problem-notes"),
    path("<uuid:pk>/incidents/", ProblemIncidentLinkView.as_view(), name="problem-link-incident"),
    path("<uuid:pk>/changes/", ProblemChangeLinkView.as_view(), name="problem-link-change"),
    # AI RCA
    path("<uuid:pk>/ai-rca/", ProblemAiRcaView.as_view(), name="problem-ai-rca"),
    # RCA Patch
    path("<uuid:pk>/rca/", ProblemRcaPatchView.as_view(), name="problem-rca-patch"),
]
