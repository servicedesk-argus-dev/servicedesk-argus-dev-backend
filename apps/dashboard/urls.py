from django.urls import path

from .views import (
    DashboardIncidentTrendView,
    DashboardSLAComplianceView,
    DashboardStatsView,
    DashboardView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("stats", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("stats/", DashboardStatsView.as_view(), name="dashboard-stats-slash"),
    path("incident-trend", DashboardIncidentTrendView.as_view(), name="dashboard-incident-trend"),
    path("incident-trend/", DashboardIncidentTrendView.as_view(), name="dashboard-incident-trend-slash"),
    path("sla-compliance", DashboardSLAComplianceView.as_view(), name="dashboard-sla-compliance"),
    path("sla-compliance/", DashboardSLAComplianceView.as_view(), name="dashboard-sla-compliance-slash"),
]
