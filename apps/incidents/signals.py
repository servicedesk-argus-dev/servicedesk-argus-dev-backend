from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Incident
from apps.notifications.services import broadcast_notification
from apps.notifications.realtime import emit_record_event

@receiver(pre_save, sender=Incident)
def incident_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            previous = Incident.objects.get(pk=instance.pk)
            instance._previous_state = previous.state
            instance._previous_assigned_to = previous.assigned_to
        except Incident.DoesNotExist:
            instance._previous_state = None
            instance._previous_assigned_to = None
    else:
        instance._previous_state = None
        instance._previous_assigned_to = None

@receiver(post_save, sender=Incident)
def incident_post_save(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: emit_record_event(
            "incident",
            instance,
            "created" if created else "updated",
        )
    )
    if created:
        broadcast_notification(
            organization=instance.organization,
            message=f"New Incident Created: {instance.number} - {instance.short_description}",
            resource_type="INCIDENT",
            resource_id=instance.id
        )
    else:
        # State change notifications
        if hasattr(instance, '_previous_state') and instance._previous_state != instance.state:
            message = f"Incident {instance.number} state changed to {instance.state}"
            broadcast_notification(
                organization=instance.organization,
                message=message,
                resource_type="INCIDENT",
                resource_id=instance.id
            )
            
            if instance.state == Incident.State.RESOLVED:
                # Notify creator/requester
                if instance.created_by:
                    broadcast_notification(
                        organization=instance.organization,
                        message=f"Your incident {instance.number} has been RESOLVED.",
                        resource_type="INCIDENT",
                        resource_id=instance.id,
                        user=instance.created_by,
                    )
                
                # Cascade resolution to child incidents
                children = instance.child_incidents.exclude(state__in=[Incident.State.RESOLVED, Incident.State.CLOSED, Incident.State.CANCELLED])
                for child in children:
                    child.state = Incident.State.RESOLVED
                    child.resolution_code = instance.resolution_code
                    child.resolution_notes = f"Automatically resolved by parent {instance.number}: {instance.resolution_notes}"
                    child.resolved_at = instance.resolved_at
                    child.save(update_fields=['state', 'resolution_code', 'resolution_notes', 'resolved_at', 'updated_at'])
        
        # Assignment change notifications
        if hasattr(instance, '_previous_assigned_to') and instance._previous_assigned_to != instance.assigned_to:
            if instance.assigned_to:
                broadcast_notification(
                    organization=instance.organization,
                    message=f"Incident {instance.number} has been assigned to you.",
                    resource_type="INCIDENT",
                    resource_id=instance.id,
                    user=instance.assigned_to,
                )
