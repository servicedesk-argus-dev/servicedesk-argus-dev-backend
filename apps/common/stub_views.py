"""Stub API views for features not yet backed by full domain apps."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.responses import success


class StubView(APIView):
    """Generic stub for frontend-called endpoints not yet implemented."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return success([], "Not yet implemented — stub response.")

    def post(self, request, *args, **kwargs):
        return success({}, "Not yet implemented — stub response.")

    def put(self, request, *args, **kwargs):
        return success({}, "Not yet implemented — stub response.")

    def patch(self, request, *args, **kwargs):
        return success({}, "Not yet implemented — stub response.")

    def delete(self, request, *args, **kwargs):
        return success({}, "Not yet implemented — stub response.")
