from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from apps.sla.models import SLADefinition, TaskSLA
from apps.sla.evaluator import evaluate_condition
from apps.sla.business_time import business_elapsed_minutes

def process_task_slas(task):
    """
    Evaluates all SLA definitions against the given task (Incident, Problem, or Change)
    and creates, pauses, stops, or resets TaskSLA records accordingly.
    """
    now = timezone.now()
    task_type = SLADefinition.AppliesTo.INCIDENT
    if task.__class__.__name__ == 'Problem':
        task_type = SLADefinition.AppliesTo.PROBLEM
    elif task.__class__.__name__ == 'Change':
        task_type = SLADefinition.AppliesTo.CHANGE

    # 1. Get all active SLA definitions for the task's organization and type
    active_definitions = SLADefinition.objects.filter(
        organization=task.organization_id,
        applies_to=task_type,
        is_active=True
    )
    
    content_type = ContentType.objects.get_for_model(task)
    
    # We also need to get existing TaskSLAs for this task
    existing_task_slas = {
        tsla.sla_definition_id: tsla 
        for tsla in TaskSLA.objects.filter(content_type=content_type, object_id=task.id).exclude(stage=TaskSLA.Stage.CANCELLED)
    }

    for definition in active_definitions:
        task_sla = existing_task_slas.get(definition.id)
        
        # Check reset conditions first
        if task_sla and definition.reset_condition and evaluate_condition(task, definition.reset_condition):
            task_sla.stage = TaskSLA.Stage.CANCELLED
            task_sla.save(update_fields=['stage'])
            task_sla = None # Allow it to be re-evaluated for start
            
        is_start = evaluate_condition(task, definition.start_condition)
        is_pause = evaluate_condition(task, definition.pause_condition) if definition.pause_condition else False
        is_stop = evaluate_condition(task, definition.stop_condition)
        
        if not task_sla:
            if is_start and not is_stop:
                # Create new TaskSLA
                TaskSLA.objects.create(
                    content_type=content_type,
                    object_id=task.id,
                    sla_definition=definition,
                    stage=TaskSLA.Stage.PAUSED if is_pause else TaskSLA.Stage.IN_PROGRESS,
                    start_time=now,
                    pause_time=now if is_pause else None
                )
        else:
            if task_sla.stage == TaskSLA.Stage.COMPLETED:
                continue # Once stopped, it stays stopped unless reset
                
            if is_stop:
                # Stop the SLA
                if task_sla.stage == TaskSLA.Stage.PAUSED and task_sla.pause_time:
                    # Accrue final pause time
                    task_sla.total_pause_duration += (now - task_sla.pause_time)
                task_sla.stage = TaskSLA.Stage.COMPLETED
                task_sla.stop_time = now
                task_sla.save(update_fields=['stage', 'stop_time', 'total_pause_duration'])
                
            elif is_pause and task_sla.stage == TaskSLA.Stage.IN_PROGRESS:
                # Move to paused
                task_sla.stage = TaskSLA.Stage.PAUSED
                task_sla.pause_time = now
                task_sla.save(update_fields=['stage', 'pause_time'])
                
            elif not is_pause and task_sla.stage == TaskSLA.Stage.PAUSED:
                # Resume from paused
                if task_sla.pause_time:
                    task_sla.total_pause_duration += (now - task_sla.pause_time)
                task_sla.stage = TaskSLA.Stage.IN_PROGRESS
                task_sla.pause_time = None
                task_sla.save(update_fields=['stage', 'pause_time', 'total_pause_duration'])
                
    # Calculate elapsed time and breach status for all SLAs
    update_task_sla_calculations(task)

def update_task_sla_calculations(task):
    now = timezone.now()
    any_breached = False
    content_type = ContentType.objects.get_for_model(task)
    
    task_slas = TaskSLA.objects.filter(content_type=content_type, object_id=task.id).select_related('sla_definition')
    for tsla in task_slas:
        if tsla.stage == TaskSLA.Stage.CANCELLED:
            continue
            
        calc_end_time = tsla.stop_time or now
        
        # Calculate gross duration
        gross_duration = calc_end_time - tsla.start_time
        
        # Subtract pause duration
        total_pause = tsla.total_pause_duration
        if tsla.stage == TaskSLA.Stage.PAUSED and tsla.pause_time:
            total_pause += (calc_end_time - tsla.pause_time)
            
        net_duration = gross_duration - total_pause
        net_minutes = max(0, int(net_duration.total_seconds() / 60))
        
        if tsla.sla_definition.business_hours_only:
            # Simplistic approximation for business hours minus pause
            bus_minutes = business_elapsed_minutes(tsla.start_time, calc_end_time, task.organization)
            pause_minutes = int(total_pause.total_seconds() / 60)
            net_minutes = max(0, bus_minutes - pause_minutes)
            
        target_minutes = tsla.sla_definition.resolution_time_minutes 
        
        tsla.business_elapsed_time = timezone.timedelta(minutes=net_minutes)
        if target_minutes > 0:
            tsla.percentage_elapsed = (net_minutes / target_minutes) * 100
        
        tsla.has_breached = net_minutes > target_minutes
        
        # ─── Escalations / Notifications ───────────────────────────────────
        from apps.notifications.services import broadcast_notification
        
        thresholds = [50, 75, 100]
        for threshold in thresholds:
            if tsla.percentage_elapsed >= threshold and threshold not in tsla.notified_thresholds:
                msg = f"SLA Warning: {tsla.sla_definition.name} for {task.number} is at {threshold}%."
                if threshold == 100:
                    msg = f"SLA BREACHED: {tsla.sla_definition.name} for {task.number} has exceeded its target."
                
                broadcast_notification(
                    organization=task.organization,
                    message=msg,
                    resource_type="SLA",
                    resource_id=tsla.id
                )
                tsla.notified_thresholds.append(threshold)
        
        tsla.save(update_fields=['business_elapsed_time', 'percentage_elapsed', 'has_breached', 'notified_thresholds'])
        
        if tsla.has_breached:
            any_breached = True
            
    # Denormalize boolean to task if field exists
    if hasattr(task, 'sla_breached') and any_breached != task.sla_breached:
        task.sla_breached = any_breached
        task.save(update_fields=['sla_breached'])
