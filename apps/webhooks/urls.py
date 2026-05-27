from django.urls import path

from .views import LinkedEyeIncidentWebhookView


urlpatterns = [
    path("linkedeye/incident/", LinkedEyeIncidentWebhookView.as_view(), name="linkedeye-incident-webhook"),
]
