import ipaddress
import secrets
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.assets.models import AssetSite, ConfigurationItem
from apps.common.responses import failure, success
from apps.common.utils import generate_record_number
from apps.incidents.models import Activity, Incident, WorkNote
from apps.organizations.models import Organization
from apps.sla.services import get_sla_targets
from apps.teams.models import Team


User = get_user_model()

OPEN_INCIDENT_STATES = (
    Incident.State.NEW,
    Incident.State.IN_PROGRESS,
    Incident.State.ON_HOLD,
    Incident.State.ESCALATED,
)

RESOLVED_STATES = {"RESOLVED", "OK", "RECOVERY", "RECOVERED", "CLEAR", "CLEARED"}


def _first(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _truncate(value: str, limit: int) -> str:
    return value[:limit] if len(value) > limit else value


def _authorization_token(request) -> str:
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return (
        request.headers.get("X-Argus-Token")
        or request.headers.get("X-API-Key")
        or ""
    ).strip()


def _authenticate_webhook(request) -> bool:
    configured_token = getattr(settings, "ARGUS_WEBHOOK_API_TOKEN", "")
    require_token = getattr(settings, "ARGUS_WEBHOOK_REQUIRE_TOKEN", False)
    if not configured_token:
        return not require_token
    supplied_token = _authorization_token(request)
    return bool(supplied_token) and secrets.compare_digest(supplied_token, configured_token)


def _priority_from_payload(payload: dict[str, Any]) -> str:
    raw_priority = _first(payload, "priority")
    normalized_priority = raw_priority.upper().replace(" ", "")
    if normalized_priority in Incident.Priority.values:
        return normalized_priority
    if normalized_priority in {"1", "CRITICAL"}:
        return Incident.Priority.P1
    if normalized_priority in {"2", "HIGH"}:
        return Incident.Priority.P2
    if normalized_priority in {"3", "WARNING", "WARN", "MEDIUM"}:
        return Incident.Priority.P3
    if normalized_priority in {"4", "LOW", "INFO", "INFORMATIONAL"}:
        return Incident.Priority.P4

    severity = _first(payload, "severity").lower()
    if severity in {"critical", "p1"}:
        return Incident.Priority.P1
    if severity in {"high", "p2"}:
        return Incident.Priority.P2
    if severity in {"warning", "warn", "medium", "p3"}:
        return Incident.Priority.P3
    return Incident.Priority.P4


def _impact_urgency_for_priority(priority: str) -> tuple[str, str]:
    if priority == Incident.Priority.P1:
        return Incident.Impact.ENTERPRISE, Incident.Urgency.CRITICAL
    if priority == Incident.Priority.P2:
        return Incident.Impact.TEAM, Incident.Urgency.HIGH
    if priority == Incident.Priority.P3:
        return Incident.Impact.TEAM, Incident.Urgency.MEDIUM
    return Incident.Impact.INDIVIDUAL, Incident.Urgency.LOW


def _resolve_site(payload: dict[str, Any]) -> AssetSite | None:
    site_id = _first(payload, "site_id", "siteId")
    if site_id:
        return AssetSite.objects.select_related("organization").filter(id=site_id).first()

    site_name = _first(payload, "site_name", "siteName", "site", "sitename")
    if not site_name:
        return None

    site_slug = slugify(site_name)
    matches = AssetSite.objects.select_related("organization").filter(
        Q(name__iexact=site_name) | Q(slug__iexact=site_slug),
        organization__is_active=True,
    )
    if matches.count() == 1:
        return matches.first()
    return None


def _resolve_organization(payload: dict[str, Any]) -> tuple[Organization | None, AssetSite | None, str | None]:
    org_id = _first(payload, "organization_id", "organizationId", "org_id", "client_id", "clientId")
    if org_id:
        organization = Organization.objects.filter(id=org_id, is_active=True).first()
        return organization, None, None if organization else "organization_id does not match an active organization"

    org_slug = _first(payload, "organization_slug", "organizationSlug", "org_slug", "client_slug", "clientSlug")
    if org_slug:
        organization = Organization.objects.filter(slug=org_slug, is_active=True).first()
        return organization, None, None if organization else "organization_slug does not match an active organization"

    org_name = _first(payload, "organization_name", "organizationName", "organization", "client_name", "clientName", "client")
    if org_name:
        organizations = Organization.objects.filter(name__iexact=org_name, is_active=True)
        if organizations.count() == 1:
            return organizations.first(), None, None
        return None, None, "organization name is ambiguous or inactive"

    site = _resolve_site(payload)
    if site and site.organization:
        return site.organization, site, None

    default_slug = getattr(settings, "ARGUS_WEBHOOK_DEFAULT_ORG_SLUG", "")
    if default_slug:
        organization = Organization.objects.filter(slug=default_slug, is_active=True).first()
        return organization, None, None if organization else "default webhook organization is not active"

    return None, None, "organization_id, organization_slug, organization_name, or uniquely matching site_name is required"


def _source_alert_id(payload: dict[str, Any]) -> str:
    explicit = _first(payload, "source_alert_id", "sourceAlertId", "alert_id", "alertId", "external_id", "externalId")
    if explicit:
        return explicit

    site = _first(payload, "site_name", "siteName", "site", "sitename")
    host = _first(payload, "host", "hostname", "source_ip", "sourceIp", "ip")
    alert_name = _first(payload, "source_alert_name", "sourceAlertName", "alert_name", "alertName", "check_name", "checkName", "title", "subject")
    fallback = ":".join(part for part in [site, host, alert_name] if part)
    return fallback


def _description(payload: dict[str, Any]) -> str:
    body = _first(payload, "description", "body", "message")
    details = [
        ("Site", _first(payload, "site_name", "siteName", "site", "sitename")),
        ("Host", _first(payload, "host", "hostname")),
        ("Source IP", _first(payload, "source_ip", "sourceIp", "ip")),
        ("Severity", _first(payload, "severity")),
        ("LinkedEye state", _first(payload, "state", "status")),
    ]
    detail_lines = [f"{label}: {value}" for label, value in details if value]
    if body and detail_lines:
        return f"{body}\n\nLinkedEye details:\n" + "\n".join(detail_lines)
    if detail_lines:
        return "LinkedEye alert received.\n\nLinkedEye details:\n" + "\n".join(detail_lines)
    return body or "LinkedEye alert received."


def _find_config_item(payload: dict[str, Any], organization: Organization) -> ConfigurationItem | None:
    host = _first(payload, "host", "hostname")
    source_ip = _first(payload, "source_ip", "sourceIp", "ip")
    ci_query = ConfigurationItem.objects.filter(organization=organization)

    filters = Q()
    if host:
        filters |= Q(name__iexact=host) | Q(hostname__iexact=host) | Q(fqdn__iexact=host)
        try:
            ipaddress.ip_address(host)
            filters |= Q(ip_address=host) | Q(physical_ip_address=host) | Q(management_ip_address=host)
        except ValueError:
            pass
    if source_ip:
        try:
            ipaddress.ip_address(source_ip)
            filters |= Q(ip_address=source_ip) | Q(physical_ip_address=source_ip) | Q(management_ip_address=source_ip)
        except ValueError:
            pass

    return ci_query.filter(filters).first() if filters else None


def _noc_group(organization: Organization) -> Team | None:
    return (
        Team.objects.filter(
            Q(organization=organization) | Q(organization__isnull=True),
            is_active=True,
        )
        .filter(Q(name__iexact="NOC") | Q(name__icontains="NOC") | Q(name__icontains="L1"))
        .order_by("organization_id", "name")
        .first()
    )


def _system_user() -> User:
    email = getattr(settings, "ARGUS_WEBHOOK_SYSTEM_USER_EMAIL", "linkedeye.webhook@argus.local")
    username = email.split("@", 1)[0]
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "first_name": "LinkedEye",
            "last_name": "Webhook",
            "is_active": True,
            "is_active_member": False,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _resolve_incident(incident: Incident, actor: User, payload: dict[str, Any]) -> None:
    previous_state = incident.state
    if incident.state != Incident.State.RESOLVED:
        incident.state = Incident.State.RESOLVED
    incident.resolved_at = incident.resolved_at or timezone.now()
    incident.resolution_notes = _first(
        payload,
        "resolution_notes",
        "resolutionNotes",
        default="LinkedEye sent recovery/OK for this alert.",
    )
    incident.save(update_fields=["state", "resolved_at", "resolution_notes", "updated_at"])
    WorkNote.objects.create(
        incident=incident,
        author=actor,
        source=WorkNote.Source.SYSTEM,
        is_internal=False,
        content=incident.resolution_notes,
    )
    Activity.objects.create(
        incident=incident,
        user=actor,
        action="LINKEDEYE_RESOLVED",
        description="LinkedEye webhook resolved the incident.",
        old_value=previous_state,
        new_value=Incident.State.RESOLVED,
    )


class LinkedEyeIncidentWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not _authenticate_webhook(request):
            return failure("Unauthorized webhook token.", status_code=401)

        payload = request.data if isinstance(request.data, dict) else {}
        organization, site, org_error = _resolve_organization(payload)
        if org_error:
            return failure(org_error, status_code=400)
        if organization is None:
            return failure("Could not resolve target organization.", status_code=400)

        source_alert_id = _source_alert_id(payload)
        if not source_alert_id:
            return failure("source_alert_id is required, or provide site_name + host + alert name.", status_code=400)
        source_alert_id = _truncate(source_alert_id, 255)

        state = _first(payload, "state", "status", default="NEW").upper().replace("-", "_")
        actor = _system_user()

        with transaction.atomic():
            organization = Organization.objects.select_for_update().get(pk=organization.pk)
            existing = (
                Incident.objects.select_for_update()
                .filter(organization=organization, source_alert_id=source_alert_id)
                .exclude(state__in=[Incident.State.CLOSED, Incident.State.CANCELLED])
                .order_by("-created_at")
                .first()
            )

            if state in RESOLVED_STATES:
                if existing is None:
                    return success(
                        {"source_alert_id": source_alert_id, "action": "ignored"},
                        "no open incident matched the resolved LinkedEye alert",
                    )
                if existing.state == Incident.State.RESOLVED:
                    return success(
                        {"id": str(existing.id), "number": existing.number, "state": existing.state, "action": "already_resolved"},
                        "incident already resolved for LinkedEye alert",
                    )
                _resolve_incident(existing, actor, payload)
                return success(
                    {"id": str(existing.id), "number": existing.number, "state": existing.state, "action": "resolved"},
                    "incident resolved from LinkedEye",
                )

            if existing and existing.state in OPEN_INCIDENT_STATES:
                previous_priority = existing.priority
                priority = _priority_from_payload(payload)
                existing.priority = priority
                existing.source_alert_name = _truncate(
                    _first(payload, "source_alert_name", "sourceAlertName", "alert_name", "alertName", "check_name", "checkName", "title", "subject", default=existing.source_alert_name or existing.short_description),
                    255,
                )
                existing.description = _description(payload)
                existing.save(update_fields=["priority", "source_alert_name", "description", "updated_at"])
                if previous_priority != priority:
                    Activity.objects.create(
                        incident=existing,
                        user=actor,
                        action="LINKEDEYE_UPDATED",
                        description="LinkedEye webhook updated incident priority.",
                        old_value=previous_priority,
                        new_value=priority,
                    )
                return success(
                    {"id": str(existing.id), "number": existing.number, "state": existing.state, "action": "deduplicated"},
                    "incident already open for LinkedEye alert",
                )

            priority = _priority_from_payload(payload)
            impact, urgency = _impact_urgency_for_priority(priority)
            response_target, resolution_target = get_sla_targets(organization, priority)
            short_description = _truncate(
                _first(payload, "short_description", "shortDescription", "title", "subject", "source_alert_name", "sourceAlertName", "alert_name", "alertName", default="LinkedEye alert"),
                200,
            )
            source_alert_name = _truncate(
                _first(payload, "source_alert_name", "sourceAlertName", "alert_name", "alertName", "check_name", "checkName", default=short_description),
                255,
            )

            incident = Incident.objects.create(
                number=generate_record_number("INC", organization, "last_incident_number"),
                short_description=short_description,
                description=_description(payload),
                state=Incident.State.NEW,
                impact=impact,
                urgency=urgency,
                priority=priority,
                category=_truncate(_first(payload, "category", "check_name", "checkName", "alert_name", "alertName", default="LinkedEye Alert"), 100),
                assignment_group=_noc_group(organization),
                config_item=_find_config_item(payload, organization),
                source=Incident.Source.API,
                source_alert_id=source_alert_id,
                source_alert_name=source_alert_name,
                site=site,
                created_by=actor,
                requested_by=actor,
                organization=organization,
                sla_target_response=response_target,
                sla_target_resolution=resolution_target,
            )
            Activity.objects.create(
                incident=incident,
                user=actor,
                action="CREATED_FROM_LINKEDEYE",
                description=f"LinkedEye webhook created incident for alert {source_alert_id}.",
                new_value=Incident.State.NEW,
            )

        return success(
            {"id": str(incident.id), "number": incident.number, "state": incident.state, "action": "created"},
            "incident created from LinkedEye",
            201,
        )
