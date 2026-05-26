from datetime import timedelta

from django.utils import timezone

from apps.notifications.sla_hooks import maybe_emit_sla_resolution_notifications

from .business_time import business_elapsed_minutes
from .models import SLADefinition


DEFAULT_SLA_MINUTES = {
    "P1": {"response": 5, "resolution": 60},
    "P2": {"response": 15, "resolution": 240},
    "P3": {"response": 60, "resolution": 1440},
    "P4": {"response": 240, "resolution": 4320},
}

PRIORITY_MATRIX = {
    "ENTERPRISE": {"CRITICAL": "P1", "HIGH": "P1", "MEDIUM": "P2", "LOW": "P3"},
    "DEPARTMENT": {"CRITICAL": "P1", "HIGH": "P2", "MEDIUM": "P2", "LOW": "P3"},
    "TEAM": {"CRITICAL": "P2", "HIGH": "P2", "MEDIUM": "P3", "LOW": "P4"},
    "INDIVIDUAL": {"CRITICAL": "P2", "HIGH": "P3", "MEDIUM": "P4", "LOW": "P4"},
}


def derive_incident_priority(impact: str | None, urgency: str | None) -> str:
    return PRIORITY_MATRIX.get(impact or "TEAM", PRIORITY_MATRIX["TEAM"]).get(urgency or "MEDIUM", "P3")


def default_definition_values(priority: str, applies_to: str = SLADefinition.AppliesTo.INCIDENT) -> dict:
    defaults = DEFAULT_SLA_MINUTES.get(priority, DEFAULT_SLA_MINUTES["P4"])
    label = {
        "P1": "Critical",
        "P2": "High",
        "P3": "Moderate",
        "P4": "Low",
    }.get(priority, "Low")

    # Define production-grade default conditions
    start_condition = {
        "condition": "AND",
        "rules": [
            {"field": "state", "operator": "in", "value": ["NEW", "IN_PROGRESS", "ESCALATED"]},
            {"field": "priority", "operator": "eq", "value": priority}
        ]
    }
    pause_condition = {
        "condition": "AND",
        "rules": [
            {"field": "state", "operator": "eq", "value": "ON_HOLD"}
        ]
    }
    stop_condition = {
        "condition": "AND",
        "rules": [
            {"field": "state", "operator": "in", "value": ["RESOLVED", "CLOSED", "CANCELLED"]}
        ]
    }

    return {
        "name": f"{priority} {label} {applies_to.title()} SLA",
        "response_time_minutes": defaults["response"],
        "resolution_time_minutes": defaults["resolution"],
        "business_hours_only": False,
        "is_active": True,
        "start_condition": start_condition,
        "pause_condition": pause_condition,
        "stop_condition": stop_condition,
    }


def ensure_default_definitions(organization, applies_to: str = SLADefinition.AppliesTo.INCIDENT) -> None:
    if organization is None:
        return
    for priority in DEFAULT_SLA_MINUTES:
        SLADefinition.objects.get_or_create(
            organization=organization,
            applies_to=applies_to,
            priority=priority,
            defaults=default_definition_values(priority, applies_to),
        )


def get_sla_definition(organization, priority: str, applies_to: str = SLADefinition.AppliesTo.INCIDENT) -> SLADefinition | None:
    if organization is None:
        return None
    ensure_default_definitions(organization, applies_to)
    return SLADefinition.objects.filter(
        organization=organization,
        applies_to=applies_to,
        priority=priority,
        is_active=True,
    ).first()


def get_sla_targets(organization, priority: str, applies_to: str = SLADefinition.AppliesTo.INCIDENT) -> tuple[timedelta, timedelta]:
    definition = get_sla_definition(organization, priority, applies_to)
    if definition:
        return (
            timedelta(minutes=definition.response_time_minutes),
            timedelta(minutes=definition.resolution_time_minutes),
        )
    defaults = DEFAULT_SLA_MINUTES.get(priority, DEFAULT_SLA_MINUTES["P4"])
    return timedelta(minutes=defaults["response"]), timedelta(minutes=defaults["resolution"])


def apply_incident_sla_targets(incident, force: bool = False):
    if force or incident.sla_target_response is None or incident.sla_target_resolution is None:
        response_target, resolution_target = get_sla_targets(incident.organization, incident.priority)
        incident.sla_target_response = response_target
        incident.sla_target_resolution = resolution_target
    return incident


def refresh_incident_sla_state(incident, previous_state: str | None = None):
    now = timezone.now()
    update_fields: list[str] = []

    if incident.state in {"IN_PROGRESS", "ON_HOLD", "ESCALATED", "RESOLVED", "CLOSED"} and incident.response_time is None:
        incident.response_time = now - incident.created_at
        update_fields.append("response_time")

    if incident.state in {"RESOLVED", "CLOSED"} and incident.resolved_at is None:
        incident.resolved_at = now
        incident.resolution_time = now - incident.created_at
        update_fields.extend(["resolved_at", "resolution_time"])

    if incident.state == "CLOSED" and incident.closed_at is None:
        incident.closed_at = now
        update_fields.append("closed_at")

    definition = (
        get_sla_definition(incident.organization, incident.priority)
        if incident.organization_id
        else None
    )
    use_business = bool(definition and definition.business_hours_only)
    target_minutes = (
        int(incident.sla_target_resolution.total_seconds() // 60) if incident.sla_target_resolution else 0
    )

    def _elapsed_minutes_for_breach() -> int:
        if not incident.sla_target_resolution:
            return 0
        if incident.resolution_time and incident.resolved_at:
            if use_business:
                return business_elapsed_minutes(incident.created_at, incident.resolved_at, incident.organization)
            return int(incident.resolution_time.total_seconds() // 60)
        if incident.state not in {"RESOLVED", "CLOSED", "CANCELLED", "ON_HOLD"}:
            if use_business:
                return business_elapsed_minutes(incident.created_at, now, incident.organization)
            return int((now - incident.created_at).total_seconds() // 60)
        return 0

    if incident.resolution_time and incident.sla_target_resolution:
        elapsed_m = _elapsed_minutes_for_breach()
        breached = elapsed_m > target_minutes
    elif incident.sla_target_resolution and incident.state not in {"RESOLVED", "CLOSED", "CANCELLED", "ON_HOLD"}:
        elapsed_m = _elapsed_minutes_for_breach()
        breached = elapsed_m > target_minutes
    else:
        elapsed_m = 0
        breached = incident.sla_breached

    if incident.sla_breached != breached:
        incident.sla_breached = breached
        update_fields.append("sla_breached")

    if incident.sla_target_resolution and incident.state not in {"RESOLVED", "CLOSED", "CANCELLED", "ON_HOLD"}:
        em = (
            business_elapsed_minutes(incident.created_at, now, incident.organization)
            if use_business
            else int((now - incident.created_at).total_seconds() // 60)
        )
        for field in maybe_emit_sla_resolution_notifications(incident, em, target_minutes):
            if field not in update_fields:
                update_fields.append(field)

    if previous_state != incident.state and incident.state not in {"RESOLVED", "CLOSED"}:
        # Keep resolved timestamps if an incident is reopened, matching ServiceNow audit behavior.
        pass

    return update_fields

