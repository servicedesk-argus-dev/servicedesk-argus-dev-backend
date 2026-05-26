from apps.integrations.tasks import notify_integrations_task
from apps.common.permissions import INTERNAL_ROLE_NAMES
from .models import Notification
from .realtime import emit_notification
from .tasks import send_email_task


RESOURCE_PATHS = {
    "INCIDENT": "incidents",
    "PROBLEM": "problems",
    "CHANGE": "changes",
    "ALERT": "alerts",
    "SERVICE_REQUEST": "service-requests",
}


def _dedupe_users(users):
    seen = set()
    result = []
    for user in users:
        user_id = getattr(user, "id", None)
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        result.append(user)
    return result


def _default_recipients(organization):
    from django.db.models import Q

    from apps.accounts.models import User

    internal_staff = User.objects.filter(is_active=True, is_active_member=True).filter(
        Q(is_superuser=True) | Q(roles__name__in=INTERNAL_ROLE_NAMES)
    )
    org_users = User.objects.none()
    if organization is not None:
        org_users = User.objects.filter(
            organization=organization,
            is_active=True,
            is_active_member=True,
        )
    return _dedupe_users(list(internal_staff.distinct()) + list(org_users.distinct()))


def _notification_type(resource_type):
    normalized = str(resource_type or "").upper()
    return normalized if normalized in Notification.Type.values else Notification.Type.SYSTEM


def _resource_link(resource_type, resource_id):
    normalized = str(resource_type or "").upper()
    path = RESOURCE_PATHS.get(normalized)
    return f"/{path}/{resource_id}" if path and resource_id else None


def create_web_notification(
    *,
    user,
    organization,
    title,
    message,
    notification_type=Notification.Type.SYSTEM,
    link=None,
):
    organization = organization or getattr(user, "organization", None)
    if user is None or organization is None:
        return None
    notification = Notification.objects.create(
        user=user,
        organization=organization,
        type=notification_type,
        title=str(title or "Argus notification")[:255],
        message=str(message or ""),
        link=link,
        channel=Notification.Channel.WEB,
    )
    emit_notification(notification)
    return notification

def broadcast_notification(
    organization,
    message,
    resource_type=None,
    resource_id=None,
    email_recipients=None,
    email_subject=None,
    email_template=None,
    email_context=None,
    user=None,
    users=None,
):
    """
    Orchestrates notifications across multiple channels.
    """
    recipients = []
    if user is not None:
        recipients.append(user)
    if users:
        recipients.extend(users)
    if not recipients:
        recipients = _default_recipients(organization)
    recipients = _dedupe_users(recipients)

    notification_type = _notification_type(resource_type)
    title = message.split(":", 1)[0][:255]
    link = _resource_link(resource_type, resource_id)

    for recipient in recipients:
        create_web_notification(
            user=recipient,
            organization=organization,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )

    # 1. Notify external integrations (Slack, Teams, etc.)
    if organization is not None:
        notify_integrations_task.delay(
            organization_id=str(organization.id),
            message=message,
            resource_type=resource_type,
            resource_id=resource_id
        )
    
    # 2. Send emails if requested
    if email_recipients and email_template:
        for email in email_recipients:
            send_email_task.delay(
                recipient_email=email,
                subject=email_subject or "Argus Notification",
                template_name=email_template,
                context=email_context or {}
            )
