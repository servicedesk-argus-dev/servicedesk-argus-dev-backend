from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notifications.services import broadcast_notification
from apps.notifications.realtime import emit_record_event

from .models import Change


@receiver(pre_save, sender=Change)
def change_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_assigned_to_id = None
        return
    instance._previous_assigned_to_id = (
        Change.objects.filter(pk=instance.pk).values_list("assigned_to_id", flat=True).first()
    )


@receiver(post_save, sender=Change)
def change_realtime_event(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: emit_record_event(
            "change",
            instance,
            "created" if created else "updated",
        )
    )
    if created:
        broadcast_notification(
            organization=instance.organization,
            message=f"New Change Created: {instance.number} - {instance.short_description}",
            resource_type="CHANGE",
            resource_id=instance.id,
        )
    elif getattr(instance, "_previous_assigned_to_id", None) != instance.assigned_to_id and instance.assigned_to:
        broadcast_notification(
            organization=instance.organization,
            message=f"Change {instance.number} has been assigned to you.",
            resource_type="CHANGE",
            resource_id=instance.id,
            user=instance.assigned_to,
        )
