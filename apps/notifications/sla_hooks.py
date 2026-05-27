"""SLA milestone web notifications (50 / 75 / 90 / 100% of resolution target)."""

from __future__ import annotations

def maybe_emit_sla_resolution_notifications(incident, elapsed_minutes: int, target_minutes: int) -> list[str]:
    """
    Create one web notification per threshold crossed (deduped on ``sla_notified_thresholds``).
    Returns extra ``update_fields`` keys the caller should persist (may be empty).
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import create_web_notification
    from apps.notifications.tasks import send_email_task

    if target_minutes <= 0:
        return []
    if incident.state in {"RESOLVED", "CLOSED", "CANCELLED", "ON_HOLD"}:
        return []

    recipient = incident.assigned_to or incident.created_by
    if recipient is None:
        return []

    notified: list[str] = list(incident.sla_notified_thresholds or [])
    pct = (elapsed_minutes / target_minutes) * 100.0
    extra_fields: list[str] = []
    changed = False

    for threshold in (50, 75, 90, 100):
        key = str(threshold)
        if pct < threshold or key in notified:
            continue
        title = f"SLA {threshold}% — {incident.number}"
        msg = (
            f"Resolution SLA for {incident.short_description[:120]} "
            f"has reached {threshold}% of the target time."
        )
        create_web_notification(
            user=recipient,
            notification_type=Notification.Type.SLA,
            title=title,
            message=msg,
            link=f"/incidents/{incident.id}",
            organization=incident.organization,
        )
        
        # Trigger async email notification
        if recipient.email:
            send_email_task.delay(
                recipient_email=recipient.email,
                subject=title,
                template_name='email/incident_notification.html',
                context={
                    'title': title,
                    'message': msg,
                    'incident_number': incident.number,
                    'incident_priority': incident.priority,
                    'incident_description': incident.short_description,
                    'incident_id': str(incident.id)
                }
            )

        notified.append(key)
        changed = True

    if changed:
        incident.sla_notified_thresholds = notified
        extra_fields.append("sla_notified_thresholds")
    return extra_fields
