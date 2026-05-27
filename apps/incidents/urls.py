from django.urls import path
from . import views

urlpatterns = [
    path("", views.IncidentListCreateView.as_view(), name="incident-list-create"),
    path("<uuid:pk>/", views.IncidentDetailView.as_view(), name="incident-detail"),
    path("<uuid:pk>/changes/", views.IncidentChangeLinkView.as_view(), name="incident-link-change"),
    path("<uuid:pk>/problems/", views.IncidentProblemLinkView.as_view(), name="incident-link-problem"),
    path("<uuid:pk>/timeline/", views.IncidentTimelineView.as_view(), name="incident-timeline"),
    path("<uuid:pk>/live-context", views.IncidentLiveContextView.as_view(), name="incident-live-context"),
    path("<uuid:pk>/live-context/", views.IncidentLiveContextView.as_view(), name="incident-live-context-slash"),
    path("stats/", views.IncidentStatsView.as_view(), name="incident-stats"),
    path("<uuid:incident_id>/work-notes/", views.WorkNoteCreateView.as_view(), name="work-note-create"),
    path("<uuid:pk>/attachments/", views.IncidentAttachmentUploadView.as_view(), name="incident-attachment-upload"),
    path("<uuid:pk>/escalate/", views.IncidentEscalateView.as_view(), name="incident-escalate"),
    path("<uuid:pk>/reassign/", views.IncidentReassignView.as_view(), name="incident-reassign"),
    # ITIL-correct lifecycle: resolve first, then close
    path("<uuid:pk>/resolve/", views.IncidentResolveView.as_view(), name="incident-resolve"),
    path("<uuid:pk>/close/", views.IncidentCloseView.as_view(), name="incident-close"),
    path("<uuid:pk>/reopen/", views.IncidentReopenView.as_view(), name="incident-reopen"),
    path("<uuid:pk>/promote-to-problem/", views.IncidentPromoteToProblemView.as_view(), name="incident-promote-problem"),
    path("bulk-update/", views.IncidentBulkUpdateView.as_view(), name="incident-bulk-update"),
    path("<uuid:pk>/child-bulk-operations/", views.IncidentChildBulkOperationsView.as_view(), name="incident-child-bulk-operations"),
    path("export/csv/", views.IncidentExportCSVView.as_view(), name="incident-export-csv"),
]
