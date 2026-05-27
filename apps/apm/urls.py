from django.urls import re_path

from apps.common.stub_views import StubView

urlpatterns = [
    re_path(r"^.*$", StubView.as_view()),
]
