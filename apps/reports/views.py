from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.alerts.models import Alert
from apps.changes.models import Change
from apps.common.responses import success
from apps.incidents.models import Incident
from apps.problems.models import Problem
from apps.teams.models import Team


def _parse_period(period_value):
    mapping = {"7d": 7, "30d": 30, "90d": 90}
    return mapping.get(period_value or "30d", 30)


class ExecutiveSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _parse_period(request.query_params.get("period"))
        since = timezone.now() - timedelta(days=days)

        incidents = Incident.objects.filter(organization=request.organization, created_at__gte=since)
        changes = Change.objects.filter(organization=request.organization, created_at__gte=since)
        problems = Problem.objects.filter(organization=request.organization)
        alerts = Alert.objects.filter(organization=request.organization)

        total_incidents = incidents.count()
        currently_open = incidents.filter(state__in=["NEW", "IN_PROGRESS", "ON_HOLD", "ESCALATED"]).count()
        p1_last_7_days = Incident.objects.filter(
            organization=request.organization,
            priority="P1",
            created_at__gte=timezone.now() - timedelta(days=7),
        ).count()

        mttr_seconds = incidents.filter(resolution_time__isnull=False).aggregate(avg=Avg("resolution_time"))["avg"]
        avg_mttr_minutes = round(mttr_seconds.total_seconds() / 60) if mttr_seconds else None

        sla_breached = incidents.filter(sla_breached=True).count()
        sla_compliance = round(((total_incidents - sla_breached) / total_incidents) * 100, 1) if total_incidents else 100.0

        completed_changes = changes.filter(state="CLOSED").count()
        successful_changes = changes.filter(state="CLOSED", closure_code="SUCCESSFUL").count()
        change_success = round((successful_changes / completed_changes) * 100, 1) if completed_changes else 100.0

        return success(
            {
                "totalIncidents": total_incidents,
                "currentlyOpen": currently_open,
                "p1Last7Days": p1_last_7_days,
                "avgMttrMinutes": avg_mttr_minutes,
                "slaCompliancePct": sla_compliance,
                "slaBreached30d": sla_breached,
                "totalChanges": changes.count(),
                "changeSuccessPct": change_success,
                "openProblems": problems.filter(state__in=["NEW", "INVESTIGATION", "RCA_IN_PROGRESS", "KNOWN_ERROR"]).count(),
                "firingAlerts": alerts.filter(status="FIRING").count(),
            }
        )


class IncidentReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _parse_period(request.query_params.get("period"))
        since = timezone.now() - timedelta(days=days)
        incidents = Incident.objects.filter(organization=request.organization, created_at__gte=since)

        by_state = list(incidents.values("state").annotate(_count=Count("id")).order_by("-_count"))
        by_priority = list(incidents.values("priority").annotate(_count=Count("id")).order_by("priority"))
        by_source = list(incidents.values("source").annotate(_count=Count("id")).order_by("-_count"))
        by_category = list(
            incidents.values("category").annotate(_count=Count("id")).order_by("-_count")
        )

        created_over_time = []
        for offset in range(days):
            day = (since + timedelta(days=offset)).date()
            count = incidents.filter(created_at__date=day).count()
            created_over_time.append({"date": day.isoformat(), "count": count})

        mttr = []
        sla_compliance = []
        for priority in ["P1", "P2", "P3", "P4"]:
            subset = incidents.filter(priority=priority)
            avg_resolution = subset.filter(resolution_time__isnull=False).aggregate(avg=Avg("resolution_time"))["avg"]
            avg_mttr_minutes = round(avg_resolution.total_seconds() / 60) if avg_resolution else 0
            resolved_count = subset.filter(state__in=["RESOLVED", "CLOSED"]).count()
            total = subset.count()
            breached = subset.filter(sla_breached=True).count()
            met = max(total - breached, 0)
            pct = round((met / total) * 100, 1) if total else 100.0
            mttr.append({"priority": priority, "avg_mttr_minutes": avg_mttr_minutes, "resolved_count": resolved_count})
            sla_compliance.append({"priority": priority, "total": total, "met": met, "compliance_pct": pct})

        return success(
            {
                "total": incidents.count(),
                "byState": by_state,
                "byPriority": by_priority,
                "bySource": by_source,
                "byCategory": by_category,
                "createdOverTime": created_over_time,
                "mttr": mttr,
                "slaCompliance": sla_compliance,
            }
        )


class IncidentTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _parse_period(request.query_params.get("period"))
        since = timezone.now() - timedelta(days=days)
        incidents = Incident.objects.filter(organization=request.organization, created_at__gte=since)
        changes = Change.objects.filter(organization=request.organization, created_at__gte=since)

        daily_counts = []
        mttr_trend = []
        for offset in range(days):
            day = (since + timedelta(days=offset)).date()
            created_count = incidents.filter(created_at__date=day).count()
            resolved_count = incidents.filter(resolved_at__date=day).count()
            avg_resolution = incidents.filter(resolved_at__date=day, resolution_time__isnull=False).aggregate(avg=Avg("resolution_time"))["avg"]
            mttr = round(avg_resolution.total_seconds() / 60) if avg_resolution else 0
            daily_counts.append({"day": day.isoformat(), "incidents": created_count, "resolved": resolved_count})
            mttr_trend.append({"day": day.isoformat(), "mttr": mttr})

        sla_rows = []
        for priority in ["P1", "P2", "P3", "P4"]:
            subset = incidents.filter(priority=priority)
            total = subset.count()
            breached = subset.filter(sla_breached=True).count()
            met = max(total - breached, 0)
            compliance = round((met / total) * 100, 1) if total else 100.0
            sla_rows.append({"priority": priority, "compliance": compliance, "target": 95})

        changes_by_type = [
            {
                "name": row["type"].title(),
                "value": row["_count"],
            }
            for row in changes.values("type").annotate(_count=Count("id")).order_by("-_count")
        ]

        return success(
            {
                "dailyCounts": daily_counts,
                "mttrTrend": mttr_trend,
                "slaCompliance": sla_rows,
                "changesByType": changes_by_type,
            }
        )


class ChangeReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _parse_period(request.query_params.get("period"))
        since = timezone.now() - timedelta(days=days)
        changes = Change.objects.filter(organization=request.organization, created_at__gte=since)

        total_completed = changes.filter(state="CLOSED").count()
        successful = changes.filter(state="CLOSED", closure_code="SUCCESSFUL").count()
        success_rate = round((successful / total_completed) * 100, 1) if total_completed else 100.0

        return success(
            {
                "total": changes.count(),
                "successRate": [
                    {
                        "total_completed": total_completed,
                        "successful": successful,
                        "success_rate": success_rate,
                    }
                ],
                "byType": list(changes.values("type").annotate(_count=Count("id")).order_by("-_count")),
                "byState": list(changes.values("state").annotate(_count=Count("id")).order_by("-_count")),
                "byRisk": [
                    {"riskLevel": row["risk_level"], "_count": row["_count"]}
                    for row in changes.values("risk_level").annotate(_count=Count("id")).order_by("-_count")
                ],
            }
        )


class TeamPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        teams = Team.objects.filter(organization=request.organization).prefetch_related("assigned_incidents")
        team_rows = []
        for team in teams:
            incidents = Incident.objects.filter(organization=request.organization, assignment_group=team)
            assigned = incidents.count()
            resolved = incidents.filter(state__in=["RESOLVED", "CLOSED"]).count()
            avg_resolution = incidents.filter(resolution_time__isnull=False).aggregate(avg=Avg("resolution_time"))["avg"]
            avg_mttr_minutes = round(avg_resolution.total_seconds() / 60) if avg_resolution else None
            breached = incidents.filter(sla_breached=True).count()
            met = max(assigned - breached, 0)
            sla = round((met / assigned) * 100, 1) if assigned else 100.0
            team_rows.append(
                {
                    "team_name": team.name,
                    "incident_count": assigned,
                    "resolved_count": resolved,
                    "avg_mttr_minutes": avg_mttr_minutes,
                    "sla_compliance": sla,
                }
            )
        return success({"teams": team_rows})

class IncidentHeatmapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _parse_period(request.query_params.get("period"))
        since = timezone.now() - timedelta(days=days)
        incidents = Incident.objects.filter(organization=request.organization, created_at__gte=since)
        
        # Heatmap data (Day of Week vs Hour of Day)
        heatmap = []
        for d in range(7): # Mon-Sun
            for h in range(24): # 0-23
                heatmap.append({"day": d, "hour": h, "count": 0})
                
        for incident in incidents:
            d = incident.created_at.weekday()
            h = incident.created_at.hour
            # Simple list find - inefficient but okay for POC
            for item in heatmap:
                if item["day"] == d and item["hour"] == h:
                    item["count"] += 1
                    break
                    
        return success({"heatmap": heatmap})
