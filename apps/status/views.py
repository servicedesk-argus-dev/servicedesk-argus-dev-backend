import time

from django.db import connection
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.common.responses import success


class StatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return success(
            {
                "status": "ok",
                "service": "argus-servicedesk-api",
                "version": "v1",
            }
        )


class MetricsView(APIView):
    """
    Lightweight operational probe: DB connectivity + simple process timing.
    Authenticated; wire your APM / Prometheus scraper to aggregate externally.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        t0 = time.perf_counter()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
            db_ok = row is not None and row[0] == 1
        except Exception as exc:
            return success(
                {
                    "db": {"ok": False, "error": str(exc)[:200]},
                    "latencyMs": round((time.perf_counter() - t0) * 1000, 2),
                }
            )
        return success(
            {
                "db": {"ok": db_ok},
                "latencyMs": round((time.perf_counter() - t0) * 1000, 2),
            }
        )
