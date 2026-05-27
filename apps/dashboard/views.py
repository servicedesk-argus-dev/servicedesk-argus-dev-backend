from datetime import date, datetime, timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.alerts.models import Alert
from apps.changes.models import Change
from apps.common.responses import success
from apps.incidents.models import Incident
from apps.problems.models import Problem


AUTOMATED_INCIDENT_SOURCES = [
    source
    for source in Incident.Source.values
    if source != Incident.Source.MANUAL
]


def _sql_day_to_date(val):
    """Postgres `date(ts)` returns `date`; SQLite may return `datetime`."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return val


def _scope_for_org(queryset, org_id):
    # Internal staff without an org context should see the full service desk.
    return queryset.filter(organization_id=org_id) if org_id else queryset


def _dashboard_payload(org_id):
    # Incident stats
    incidents = _scope_for_org(Incident.objects.all(), org_id)
    by_source = dict(incidents.values_list("source").annotate(count=Count("id")))
    manual_count = by_source.get(Incident.Source.MANUAL, 0)
    automated_count = sum(by_source.get(source, 0) for source in AUTOMATED_INCIDENT_SOURCES)
    incident_stats = {
        "total": incidents.count(),
        "manual": manual_count,
        "automated": automated_count,
        "open": incidents.filter(state__in=["NEW", "IN_PROGRESS", "ON_HOLD", "ESCALATED"]).count(),
        "p1_count": incidents.filter(priority="P1").count(),
        "p2_count": incidents.filter(priority="P2").count(),
        "p3_count": incidents.filter(priority="P3").count(),
        "p4_count": incidents.filter(priority="P4").count(),
        "sla_breached": incidents.filter(sla_breached=True).count(),
        "resolved": incidents.filter(state="RESOLVED").count(),
        "closed": incidents.filter(state="CLOSED").count(),
        "by_state": dict(incidents.values_list("state").annotate(count=Count("id"))),
        "by_priority": dict(incidents.values_list("priority").annotate(count=Count("id"))),
        "by_source": by_source,
    }

    # Change stats
    changes = _scope_for_org(Change.objects.all(), org_id)
    change_stats = {
        "total": changes.count(),
        "pending": changes.filter(state__in=["NEW", "ASSESSMENT", "APPROVAL", "SCHEDULED"]).count(),
        "implementing": changes.filter(state="IMPLEMENTING").count(),
        "success_rate": 0,
    }

    # Problem stats
    problems = _scope_for_org(Problem.objects.all(), org_id)
    problem_stats = {
        "total": problems.count(),
        "open": problems.filter(state__in=["NEW", "INVESTIGATION", "RCA_IN_PROGRESS", "KNOWN_ERROR"]).count(),
        "known_errors": problems.filter(state="KNOWN_ERROR").count(),
    }

    # Alert stats
    alerts = _scope_for_org(Alert.objects.all(), org_id)
    now = timezone.now()
    alert_stats = {
        "firing": alerts.filter(status="FIRING").count(),
        "resolved_24h": alerts.filter(status="RESOLVED", resolved_at__gte=now - timedelta(hours=24)).count(),
        "critical": alerts.filter(severity="CRITICAL").count(),
        "warning": alerts.filter(severity="WARNING").count(),
    }


    recent_incidents = incidents.order_by("-created_at")[:5]
    recent_changes = changes.order_by("-created_at")[:5]
    active_alerts = alerts.filter(status="FIRING").order_by("-fired_at")[:10]

    total_incidents = incident_stats["total"]
    sla_met = max(total_incidents - incident_stats["sla_breached"], 0)
    sla_compliance = round((sla_met / total_incidents) * 100, 1) if total_incidents else 100.0

    return {
        "kpi": {
            "openIncidents": incident_stats["open"],
            "p1Active": incident_stats["p1_count"],
            "slaBreached": incident_stats["sla_breached"],
            "activeChanges": change_stats["pending"] + change_stats["implementing"],
            "firingAlerts": alert_stats["firing"],
            "slaCompliance": sla_compliance,
            "totalIncidents": total_incidents,
            "manualIncidents": manual_count,
            "autoCreatedIncidents": automated_count,
        },
        "incidents": incident_stats,
        "changes": change_stats,
        "problems": problem_stats,
        "alerts": alert_stats,
        "recent_incidents": [
            {
                "id": str(i.id),
                "number": i.number,
                "short_description": i.short_description,
                "state": i.state,
                "priority": i.priority,
                "created_at": i.created_at.isoformat(),
            }
            for i in recent_incidents
        ],
        "recent_changes": [
            {
                "id": str(c.id),
                "number": c.number,
                "short_description": c.short_description,
                "state": c.state,
                "type": c.type,
                "created_at": c.created_at.isoformat(),
            }
            for c in recent_changes
        ],
        "active_alerts": [
            {
                "id": str(a.id),
                "alert_id": a.alert_id,
                "name": a.name,
                "severity": a.severity,
                "fired_at": a.fired_at.isoformat(),
            }
            for a in active_alerts
        ],
    }


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return success(_dashboard_payload(request.organization_id))


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success(_dashboard_payload(request.organization_id))


class DashboardIncidentTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = request.organization_id
        try:
            days = max(int(request.query_params.get("days", 7)), 1)
        except (TypeError, ValueError):
            days = 7

        since = timezone.now() - timedelta(days=days - 1)
        incidents = _scope_for_org(Incident.objects.all(), org_id).filter(created_at__gte=since)
        resolved = _scope_for_org(Incident.objects.all(), org_id).filter(resolved_at__gte=since)

        created_map = {
            _sql_day_to_date(row["day"]): row["count"]
            for row in incidents.extra({"day": "date(created_at)"}).values("day").annotate(count=Count("id"))
        }
        resolved_map = {
            _sql_day_to_date(row["day"]): row["count"]
            for row in resolved.extra({"day": "date(resolved_at)"}).values("day").annotate(count=Count("id"))
        }

        data = []
        for offset in range(days):
            day = (since + timedelta(days=offset)).date()
            data.append(
                {
                    "day": day.isoformat(),
                    "incidents": created_map.get(day, 0),
                    "resolved": resolved_map.get(day, 0),
                }
            )
        return success(data)


class DashboardSLAComplianceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = request.organization_id
        incidents = _scope_for_org(Incident.objects.all(), org_id)
        rows = []
        for priority in ["P1", "P2", "P3", "P4"]:
            total = incidents.filter(priority=priority).count()
            breached = incidents.filter(priority=priority, sla_breached=True).count()
            met = max(total - breached, 0)
            compliance = round((met / total) * 100, 1) if total else 100.0
            rows.append({"priority": priority, "compliance": compliance, "target": 95, "total": total, "met": met})
        return success(rows)
