"""Celery tasks for SLA maintenance (schedule via beat in production)."""

from celery import shared_task


@shared_task(name="sla.sweep_all_task_slas")
def sweep_all_task_slas() -> int:
    """
    Recompute SLA breach flags for all open tasks (Incidents, Problems, Changes).
    """
    from apps.incidents.models import Incident
    from apps.problems.models import Problem
    from apps.changes.models import Change
    from apps.sla.engine import process_task_slas

    updated = 0
    
    # 1. Sweep Incidents
    incidents = Incident.objects.filter(
        state__in=["NEW", "IN_PROGRESS", "ESCALATED", "ON_HOLD"]
    )
    for incident in incidents.iterator():
        process_task_slas(incident)
        updated += 1
        
    # 2. Sweep Problems
    problems = Problem.objects.filter(
        state__in=["NEW", "INVESTIGATION", "RCA_IN_PROGRESS"]
    )
    for problem in problems.iterator():
        process_task_slas(problem)
        updated += 1
        
    # 3. Sweep Changes
    changes = Change.objects.filter(
        state__in=["NEW", "ASSESS", "AUTHORIZE", "SCHEDULED", "IMPLEMENT"]
    )
    for change in changes.iterator():
        process_task_slas(change)
        updated += 1
        
    return updated
