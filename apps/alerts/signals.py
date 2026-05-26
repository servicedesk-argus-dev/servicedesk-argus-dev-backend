from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notifications.services import broadcast_notification
from apps.notifications.realtime import emit_record_event

from .models import Alert


@receiver(pre_save, sender=Alert)
def alert_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = Alert.objects.filter(pk=instance.pk).values_list("status", flat=True).first()


@receiver(post_save, sender=Alert)
def alert_realtime_event(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "_previous_status", None)
    if created or instance.status == Alert.Status.FIRING:
        action = "fired"
    elif previous_status != instance.status and instance.status == Alert.Status.RESOLVED:
        action = "resolved"
    elif previous_status != instance.status and instance.status == Alert.Status.ACKNOWLEDGED:
        action = "acknowledged"
    else:
        action = "fired"
    transaction.on_commit(lambda: emit_record_event("alert", instance, action))
    if created and instance.status == Alert.Status.FIRING:
        broadcast_notification(
            organization=instance.organization,
            message=f"Alert Fired: {instance.name}",
            resource_type="ALERT",
            resource_id=instance.id,
        )
    elif previous_status != instance.status and instance.status == Alert.Status.RESOLVED:
        broadcast_notification(
            organization=instance.organization,
            message=f"Alert Resolved: {instance.name}",
            resource_type="ALERT",
            resource_id=instance.id,
        )
