from django.urls import path

from .views import (
    ChangeReportView,
    ExecutiveSummaryView,
    IncidentReportView,
    IncidentTrendView,
    TeamPerformanceView,
    IncidentHeatmapView,
)

urlpatterns = [
    path("executive-summary", ExecutiveSummaryView.as_view(), name="reports-executive-summary"),
    path("incidents", IncidentReportView.as_view(), name="reports-incidents"),
    path("incident-trend", IncidentTrendView.as_view(), name="reports-incident-trend"),
    path("changes", ChangeReportView.as_view(), name="reports-changes"),
    path("team-performance", TeamPerformanceView.as_view(), name="reports-team-performance"),
    path("heatmap", IncidentHeatmapView.as_view(), name="reports-heatmap"),
]
