import json
from datetime import datetime
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import ConfigurationItem
from apps.incidents.models import Incident, UnmatchedAlert


SEVERITY_TO_PRIORITY = {
    "critical": Incident.Priority.P1,
    "high": Incident.Priority.P2,
    "warning": Incident.Priority.P3,
    "medium": Incident.Priority.P3,
    "low": Incident.Priority.P4,
    "info": Incident.Priority.P4,
}


def parse_timestamp(value):
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.utc)
        return parsed
    except Exception:
        return None


def next_incident_number():
    timestamp = timezone.now()
    prefix = f"INC{timestamp.year}"
    suffix = timestamp.strftime("%m%d%H%M%S%f")[-8:]
    return f"{prefix}{suffix}"


class Command(BaseCommand):
    help = "Synchronize Alertmanager alerts into incidents."

    def handle(self, *args, **options):
        endpoint = urljoin(settings.ALERTMANAGER_URL.rstrip("/") + "/", "api/v2/alerts")
        try:
            with urlopen(endpoint, timeout=10) as response:
                alerts = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.stderr.write(f"Failed to fetch alerts from Alertmanager: {exc}")
            self.stdout.write("Processed 0 alerts, created 0, updated 0, unmatched 0.")
            return

        processed = 0
        created = 0
        updated = 0
        unmatched = 0

        for alert in alerts:
            processed += 1
            try:
                labels = alert.get("labels") or {}
                annotations = alert.get("annotations") or {}
                status = alert.get("status") or {}
                ci_id = labels.get("ci_id")
                alert_name = labels.get("alertname") or labels.get("alert_name") or "Unknown alert"

                if not ci_id:
                    UnmatchedAlert.objects.create(
                        raw_payload=alert,
                        alert_name=alert_name,
                        reason="missing_ci_id",
                    )
                    unmatched += 1
                    continue

                ci = ConfigurationItem.all_objects.filter(id=ci_id).select_related("organization").first()
                if ci is None:
                    UnmatchedAlert.objects.create(
                        raw_payload=alert,
                        alert_name=alert_name,
                        reason="ci_not_found",
                    )
                    unmatched += 1
                    continue

                created_by = (
                    User.objects.filter(organization=ci.organization).order_by("created_at").first()
                    or User.objects.order_by("created_at").first()
                )
                if created_by is None:
                    raise RuntimeError("No available user exists to own synced incidents")

                severity = (labels.get("severity") or "warning").lower()
                state = Incident.State.RESOLVED if status.get("state") == "resolved" else Incident.State.IN_PROGRESS

                description = json.dumps(
                    {
                        "labels": labels,
                        "annotations": annotations,
                        "generatorURL": alert.get("generatorURL"),
                    },
                    sort_keys=True,
                )

                incident, was_created = Incident.objects.get_or_create(
                    config_item=ci,
                    source_alert_name=alert_name,
                    organization=ci.organization,
                    defaults={
                        "number": next_incident_number(),
                        "short_description": alert_name,
                        "description": description,
                        "state": state,
                        "priority": SEVERITY_TO_PRIORITY.get(severity, Incident.Priority.P3),
                        "impact": Incident.Impact.TEAM,
                        "urgency": Incident.Urgency.HIGH if severity in {"critical", "high"} else Incident.Urgency.MEDIUM,
                        "created_by": created_by,
                        "config_item": ci,
                        "organization": ci.organization,
                        "source": Incident.Source.PROMETHEUS,
                        "source_alert_id": alert.get("fingerprint") or labels.get("fingerprint"),
                        "source_alert_name": alert_name,
                        "resolved_at": parse_timestamp(alert.get("endsAt")) if status.get("state") == "resolved" else None,
                    },
                )

                if was_created:
                    created += 1
                else:
                    incident.short_description = alert_name
                    incident.description = description
                    incident.state = state
                    incident.priority = SEVERITY_TO_PRIORITY.get(severity, Incident.Priority.P3)
                    incident.impact = Incident.Impact.TEAM
                    incident.urgency = Incident.Urgency.HIGH if severity in {"critical", "high"} else Incident.Urgency.MEDIUM
                    incident.source = Incident.Source.PROMETHEUS
                    incident.source_alert_id = alert.get("fingerprint") or labels.get("fingerprint")
                    incident.resolved_at = parse_timestamp(alert.get("endsAt")) if status.get("state") == "resolved" else None
                    incident.save(update_fields=[
                        "short_description",
                        "description",
                        "state",
                        "priority",
                        "impact",
                        "urgency",
                        "source",
                        "source_alert_id",
                        "resolved_at",
                        "updated_at",
                    ])
                    updated += 1
            except Exception as exc:
                self.stderr.write(f"Failed to process alert: {exc}")
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} alerts, created {created}, updated {updated}, unmatched {unmatched}."
            )
        )
