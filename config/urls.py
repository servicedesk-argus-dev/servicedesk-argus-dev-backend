from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.common.responses import success
from apps.common.stub_views import StubView


def health(_request):
    return JsonResponse({"status": "ok"})


SVG_TEMPLATE_LIST = [
    {"id": "dell-poweredge-r650", "manufacturer": "Dell", "model": "PowerEdge R650", "isStack": False, "category": "server"},
    {"id": "dell-poweredge-r550", "manufacturer": "Dell", "model": "PowerEdge R550", "isStack": False, "category": "server"},
    {"id": "cisco-nexus-93180yc-fx", "manufacturer": "Cisco", "model": "Nexus 93180YC-FX", "isStack": False, "category": "switch"},
    {"id": "cisco-asr-1001-x", "manufacturer": "Cisco", "model": "ASR 1001-X", "isStack": False, "category": "router"},
    {"id": "palo-alto-pa-3220", "manufacturer": "Palo Alto", "model": "PA-3220", "isStack": False, "category": "firewall"},
    {"id": "f5-big-ip-ve", "manufacturer": "F5", "model": "BIG-IP VE", "isStack": False, "category": "load-balancer"},
    {"id": "netapp-aff-a250", "manufacturer": "NetApp", "model": "AFF A250", "isStack": False, "category": "storage"},
    {"id": "vmware-vsphere-cluster", "manufacturer": "VMware", "model": "vSphere Cluster", "isStack": True, "category": "virtualization"},
    {"id": "apc-smart-ups-3000", "manufacturer": "APC", "model": "Smart-UPS 3000", "isStack": False, "category": "power"},
]


def _device_svg(template_id):
    title = template_id.replace("-", " ").title()
    port_rects = []
    for index in range(12):
        x = 210 + (index * 34)
        cls = "pmgmt-01" if index == 0 else f"pport-{index:02d}"
        fill = "#10b981" if index % 4 != 0 else "#f59e0b"
        port_rects.append(
            f'<g class="{cls}"><title>Port {index + 1}</title>'
            f'<rect x="{x}" y="118" width="22" height="18" rx="3" fill="{fill}" opacity="0.9"/>'
            f'<rect x="{x + 5}" y="123" width="12" height="3" rx="1" fill="#0f172a" opacity="0.45"/></g>'
        )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 260" role="img" aria-label="{title} diagram">
  <defs>
    <linearGradient id="face" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#334155"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#020617" flood-opacity="0.35"/>
    </filter>
  </defs>
  <rect width="720" height="260" rx="20" fill="#0f172a"/>
  <rect x="58" y="72" width="604" height="118" rx="16" fill="url(#face)" stroke="#475569" filter="url(#shadow)"/>
  <rect x="78" y="92" width="92" height="62" rx="8" fill="#020617" stroke="#475569"/>
  <circle cx="98" cy="112" r="6" fill="#10b981"/>
  <circle cx="120" cy="112" r="6" fill="#10b981"/>
  <circle cx="142" cy="112" r="6" fill="#f59e0b"/>
  <text x="78" y="177" fill="#cbd5e1" font-family="Inter, Arial, sans-serif" font-size="15" font-weight="700">{title}</text>
  <text x="78" y="199" fill="#64748b" font-family="Inter, Arial, sans-serif" font-size="12">Interactive port layout</text>
  {''.join(port_rects)}
  <g class="pwan-01"><title>WAN Uplink</title><rect x="604" y="104" width="34" height="44" rx="6" fill="#f59e0b"/></g>
  <g class="pha-01"><title>HA Sync</title><rect x="554" y="104" width="34" height="44" rx="6" fill="#8b5cf6"/></g>
</svg>
""".strip()


class SvgTemplateListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success(SVG_TEMPLATE_LIST)


class SvgTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, template_id):
        match = next((item for item in SVG_TEMPLATE_LIST if item["id"] == template_id), None)
        if match is None:
            return success({"templateId": template_id, "svgContent": "", "portStates": {}})

        return success(
            {
                "templateId": template_id,
                "svgContent": _device_svg(template_id),
                "portStates": {
                    "pmgmt-01": {"status": "up", "role": "management"},
                    "pwan-01": {"status": "up", "role": "wan"},
                    "pha-01": {"status": "standby", "role": "ha"},
                },
            }
        )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/organizations/", include("apps.organizations.urls")),
    path("api/v1/incidents/", include("apps.incidents.urls")),
    path("api/v1/changes/", include("apps.changes.urls")),
    path("api/v1/problems/", include("apps.problems.urls")),
    path("api/v1/sla/", include("apps.sla.urls")),
    path("api/v1/alerts/", include("apps.alerts.urls")),
    path("api/v1/assets/", include("apps.assets.urls")),
    path("api/v1/teams/", include("apps.teams.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/v1/integrations/", include("apps.integrations.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/search/", include("apps.search.urls")),
    path("api/v1/audit/", include("apps.common.urls")),
    path("api/v1/workflows/", include("apps.workflows.urls")),
    path("api/v1/automations/", include("apps.automations.urls")),
    path("api/v1/approvals/", include("apps.approvals.urls")),
    path("api/v1/assignments/", include("apps.assignments.urls")),
    path("api/v1/learning/", include("apps.learning.urls")),
    path("api/v1/", include("apps.service_catalog.urls")),
    path("api/v1/apm/", include("apps.apm.urls")),
    path("api/v1/eod/", include("apps.eod.urls")),
    path("api/v1/ill-bandwidth/", include("apps.illbandwidth.urls")),
    path("api/v1/oms/", include("apps.oms.urls")),
    path("api/v1/webhooks/", include("apps.webhooks.urls")),
    path("api/v1/status/", include("apps.status.urls")),
    path("api/v1/health/", health),
    path("api/v1/svg-templates/", SvgTemplateListView.as_view()),
    path("api/v1/svg-templates/<slug:template_id>/", SvgTemplateDetailView.as_view()),
    # Stub endpoints for frontend features not yet implemented on backend
    path("api/v1/ai/infrastructure-metrics/", StubView.as_view()),
    path("api/v1/ai/infrastructure-metrics", StubView.as_view()),
    path("api/v1/ai/classifications/", StubView.as_view()),
    path("api/v1/ai/classifications", StubView.as_view()),
    path("api/v1/ai/suggestions/", StubView.as_view()),
    path("api/v1/ai/suggestions", StubView.as_view()),
    path("api/v1/ai/tips/", StubView.as_view()),
    path("api/v1/ai/tips", StubView.as_view()),
    path("api/v1/ai/stats/", StubView.as_view()),
    path("api/v1/ai/stats", StubView.as_view()),
    path("api/v1/bod-eod/overview/", StubView.as_view()),
    path("api/v1/bod-eod/overview", StubView.as_view()),
]
