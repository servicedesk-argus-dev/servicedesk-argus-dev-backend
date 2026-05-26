from django.urls import path
from .views import IntegrationListCreateView, IntegrationDetailView, IntegrationTestView

urlpatterns = [
    path("", IntegrationListCreateView.as_view()),
    path("<uuid:pk>/test/", IntegrationTestView.as_view()),
    path("<uuid:pk>/test", IntegrationTestView.as_view()),
    path("<uuid:pk>/", IntegrationDetailView.as_view()),
    path("<uuid:pk>", IntegrationDetailView.as_view()),
]
