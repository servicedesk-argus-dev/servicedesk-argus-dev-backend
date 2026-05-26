from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notifications.services import broadcast_notification
from apps.notifications.realtime import emit_record_event

from .models import ServiceRequest


@receiver(pre_save, sender=ServiceRequest)
def service_request_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_assigned_to_id = None
        instance._previous_state = None
        return
    previous = ServiceRequest.objects.filter(pk=instance.pk).values("assigned_to_id", "state").first() or {}
    instance._previous_assigned_to_id = previous.get("assigned_to_id")
    instance._previous_state = previous.get("state")


@receiver(post_save, sender=ServiceRequest)
def service_request_realtime_event(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: emit_record_event(
            "service_request",
            instance,
            "created" if created else "updated",
        )
    )
    if created:
        broadcast_notification(
            organization=instance.organization,
            message=f"New Service Request Created: {instance.number} - {instance.short_description}",
            resource_type="SERVICE_REQUEST",
            resource_id=instance.id,
        )
        return
    if getattr(instance, "_previous_assigned_to_id", None) != instance.assigned_to_id and instance.assigned_to:
        broadcast_notification(
            organization=instance.organization,
            message=f"Service request {instance.number} has been assigned to you.",
            resource_type="SERVICE_REQUEST",
            resource_id=instance.id,
            user=instance.assigned_to,
        )
    if getattr(instance, "_previous_state", None) != instance.state and instance.state in {
        ServiceRequest.State.FULFILLED,
        ServiceRequest.State.CLOSED,
        ServiceRequest.State.CANCELLED,
    }:
        recipients = [instance.opened_by, instance.requested_for]
        broadcast_notification(
            organization=instance.organization,
            message=f"Service request {instance.number} is now {instance.state}.",
            resource_type="SERVICE_REQUEST",
            resource_id=instance.id,
            users=[user for user in recipients if user],
        )
