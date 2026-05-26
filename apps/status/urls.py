from django.urls import path

from .views import MetricsView, StatusView

urlpatterns = [
    path("", StatusView.as_view()),
    path("metrics/", MetricsView.as_view()),
]
