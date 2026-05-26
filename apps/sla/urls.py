from django.urls import path

from .views import SLADefinitionDetailView, SLADefinitionListView, TaskSLAListView

urlpatterns = [
    path("", SLADefinitionListView.as_view(), name="sla-definition-list"),
    path("incidents/<uuid:incident_id>/task-slas/", TaskSLAListView.as_view(), name="incident-task-sla-list"),
    path("<str:priority>", SLADefinitionDetailView.as_view(), name="sla-definition-detail"),
    path("<str:priority>/", SLADefinitionDetailView.as_view(), name="sla-definition-detail-slash"),
]

