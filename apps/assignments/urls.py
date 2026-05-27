from django.urls import path
from . import views

urlpatterns = [
    path("rules/", views.AssignmentRuleListCreateView.as_view(), name="assignment-rule-list"),
    path("rules/<uuid:pk>/", views.AssignmentRuleDetailView.as_view(), name="assignment-rule-detail"),
    path("category-mappings/", views.CategoryGroupMappingListCreateView.as_view(), name="category-mapping-list"),
    path("category-mappings/<uuid:pk>/", views.CategoryGroupMappingDetailView.as_view(), name="category-mapping-detail"),
    path("skills/", views.UserSkillListCreateView.as_view(), name="user-skill-list"),
    path("skill-requirements/", views.SkillRequirementListCreateView.as_view(), name="skill-requirement-list"),
    path("preview/", views.AssignmentPreviewView.as_view(), name="assignment-preview"),
    path("teams/<uuid:team_id>/members/", views.TeamMembersFilteredView.as_view(), name="team-members-filtered"),
]
