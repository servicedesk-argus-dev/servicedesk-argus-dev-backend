from django.urls import path
from .views import ChangeApprovalDecisionView, ChangeListCreateView, ChangeDetailView, ApprovalCreateView

urlpatterns = [
    path("", ChangeListCreateView.as_view(), name="change-list-create"),
    path("<uuid:pk>/", ChangeDetailView.as_view(), name="change-detail"),
    path("<uuid:change_id>/approvals/", ApprovalCreateView.as_view(), name="approval-create"),
    path("<uuid:change_id>/approvals/decision/", ChangeApprovalDecisionView.as_view(), name="approval-decision"),
]
