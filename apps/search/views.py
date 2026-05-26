from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.alerts.models import Alert
from apps.changes.models import Change
from apps.common.responses import success
from apps.incidents.models import Incident
from apps.problems.models import Problem
from apps.teams.models import Team


def _request_organization(request):
    return getattr(request, "organization", None)


def _limit(request):
    try:
        value = int(request.query_params.get("limit", 10))
    except (TypeError, ValueError):
        value = 10
    return min(max(value, 1), 50)


def _item(item_id, kind, title, subtitle, url, extra=None):
    payload = {
        "id": str(item_id),
        "type": kind,
        "title": title,
        "subtitle": subtitle,
        "url": url,
    }
    if extra:
        payload.update(extra)
    return payload


class SearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or request.query_params.get("query") or "").strip()
        limit = _limit(request)
        organization = _request_organization(request)

        groups = {
            "incidents": [],
            "problems": [],
            "changes": [],
            "alerts": [],
            "teams": [],
        }

        if not query or organization is None:
            return success({"query": query, "total": 0, "results": [], "groups": groups})

        incidents = (
            Incident.objects.filter(organization=organization)
            .filter(
                Q(number__icontains=query)
                | Q(short_description__icontains=query)
                | Q(description__icontains=query)
                | Q(category__icontains=query)
                | Q(subcategory__icontains=query)
                | Q(source__icontains=query)
                | Q(state__icontains=query)
                | Q(priority__icontains=query)
                | Q(assigned_to__email__icontains=query)
                | Q(assigned_to__first_name__icontains=query)
                | Q(assigned_to__last_name__icontains=query)
                | Q(assignment_group__name__icontains=query)
            )
            .select_related("assigned_to", "assignment_group")
            .order_by("-created_at")[:limit]
        )
        groups["incidents"] = [
            _item(
                incident.id,
                "incident",
                incident.number,
                f"{incident.short_description} · {incident.priority} · {incident.state}",
                f"/incidents/{incident.id}",
            )
            for incident in incidents
        ]

        problems = (
            Problem.objects.filter(organization=organization)
            .filter(
                Q(number__icontains=query)
                | Q(short_description__icontains=query)
                | Q(description__icontains=query)
                | Q(category__icontains=query)
                | Q(state__icontains=query)
                | Q(priority__icontains=query)
            )
            .order_by("-created_at")[:limit]
        )
        groups["problems"] = [
            _item(
                problem.id,
                "problem",
                problem.number,
                f"{problem.short_description} · {problem.priority} · {problem.state}",
                f"/problems/{problem.id}",
            )
            for problem in problems
        ]

        changes = (
            Change.objects.filter(organization=organization)
            .filter(
                Q(number__icontains=query)
                | Q(short_description__icontains=query)
                | Q(description__icontains=query)
                | Q(category__icontains=query)
                | Q(state__icontains=query)
                | Q(type__icontains=query)
                | Q(risk_level__icontains=query)
            )
            .order_by("-created_at")[:limit]
        )
        groups["changes"] = [
            _item(
                change.id,
                "change",
                change.number,
                f"{change.short_description} · {change.type} · {change.state}",
                f"/changes/{change.id}",
            )
            for change in changes
        ]


        alerts = (
            Alert.objects.filter(organization=organization)
            .filter(
                Q(alert_id__icontains=query)
                | Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(severity__icontains=query)
                | Q(status__icontains=query)
                | Q(source__icontains=query)
            )
            .order_by("-fired_at")[:limit]
        )
        groups["alerts"] = [
            _item(
                alert.id,
                "alert",
                alert.name,
                f"{alert.severity} · {alert.status} · {alert.source}",
                f"/alerts/{alert.id}",
            )
            for alert in alerts
        ]

        teams = (
            Team.objects.filter(organization=organization)
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(email__icontains=query)
                | Q(slack_channel__icontains=query)
            )
            .order_by("name")[:limit]
        )
        groups["teams"] = [
            _item(team.id, "team", team.name, team.email or "N/A", f"/settings/teams/{team.id}")
            for team in teams
        ]

        results = []
        for group_items in groups.values():
            results.extend(group_items)

        return success({"query": query, "total": len(results), "results": results, "groups": groups})
