from celery import shared_task
from django.utils import timezone
from .models import Incident
from apps.teams.models import EscalationPolicy, EscalationStep
from apps.notifications.services import broadcast_notification
from apps.common.activity_log import create_activity

@shared_task(name="incidents.check_escalations")
def check_escalations():
    """
    Checks for incidents that have exceeded escalation step wait times.
    """
    now = timezone.now()
    # Only check open incidents
    open_incidents = Incident.objects.filter(
        state__in=[Incident.State.NEW, Incident.State.IN_PROGRESS, Incident.State.ON_HOLD],
        assignment_group__isnull=False
    )
    
    for incident in open_incidents:
        policy = EscalationPolicy.objects.filter(
            team=incident.assignment_group,
            is_default=True
        ).first()
        
        if not policy:
            continue
            
        # Get the current escalation level from activity or a field
        # For simplicity, we'll check how long it's been since created or last activity
        elapsed = (now - incident.updated_at).total_seconds() / 60
        
        # Check steps
        steps = policy.steps.order_by('step_number')
        for step in steps:
            if elapsed > step.wait_time_minutes:
                # Potential escalation logic:
                # 1. Notify users/roles in the step
                # 2. Mark incident as escalated if it's the first step or a specific threshold
                
                # Check if we already escalated for this step (to avoid spam)
                # We can check activity log
                already_escalated = incident.activities.filter(
                    action="ESCALATED", 
                    description__icontains=f"Step {step.step_number}"
                ).exists()
                
                if not already_escalated:
                    incident.state = Incident.State.ESCALATED
                    incident.save(update_fields=['state', 'updated_at'])
                    
                    create_activity(
                        request=None,
                        action="ESCALATED",
                        description=f"Auto-escalated by Policy: {policy.name} (Step {step.step_number})",
                        user=None, # System action
                        incident=incident
                    )
                    
                    # Notify
                    for user in step.notify_users.all():
                        broadcast_notification(
                            organization=incident.organization,
                            message=f"Critical Escalation: Incident {incident.number} requires immediate attention.",
                            resource_type="INCIDENT",
                            resource_id=incident.id,
                            user=user
                        )
                    break # Only do one step at a time per check
    return "Escalation check complete"
