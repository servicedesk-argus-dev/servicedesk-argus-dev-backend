from django.urls import path

from .views import (
    OnCallOverviewView,
    TeamDetailView,
    TeamEscalationView,
    TeamListCreateView,
    TeamMemberCreateView,
    TeamOnCallHistoryView,
    TeamOnCallView,
)

urlpatterns = [
    path("", TeamListCreateView.as_view(), name="team-list-create"),
    path("on-call/overview", OnCallOverviewView.as_view(), name="team-oncall-overview"),
    path("on-call/overview/", OnCallOverviewView.as_view(), name="team-oncall-overview-slash"),
    path("<uuid:pk>/", TeamDetailView.as_view(), name="team-detail"),
    path("<uuid:team_id>/on-call", TeamOnCallView.as_view(), name="team-oncall"),
    path("<uuid:team_id>/on-call/", TeamOnCallView.as_view(), name="team-oncall-slash"),
    path("<uuid:team_id>/on-call/history", TeamOnCallHistoryView.as_view(), name="team-oncall-history"),
    path("<uuid:team_id>/on-call/history/", TeamOnCallHistoryView.as_view(), name="team-oncall-history-slash"),
    path("<uuid:team_id>/escalation", TeamEscalationView.as_view(), name="team-escalation"),
    path("<uuid:team_id>/escalation/", TeamEscalationView.as_view(), name="team-escalation-slash"),
    path("<uuid:team_id>/members/", TeamMemberCreateView.as_view(), name="team-member-create"),
]
