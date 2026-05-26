from apps.automations.models import AutomationRule

def process_automations(obj, trigger_event):
    """
    Finds and executes active automation rules for the given object and trigger event.
    """
    from django.contrib.contenttypes.models import ContentType
    content_type = ContentType.objects.get_for_model(obj)
    model_name = f"{content_type.app_label}.{content_type.model_class().__name__}"
    
    rules = AutomationRule.objects.filter(
        organization=obj.organization,
        target_model=model_name,
        trigger=trigger_event,
        is_active=True
    ).order_by('priority')
    
    for rule in rules:
        if evaluate_automation_conditions(obj, rule.conditions):
            execute_automation_actions(obj, rule.actions)

def evaluate_automation_conditions(obj, conditions):
    """
    Evaluates JSON-based conditions for automation rules.
    """
    if not conditions:
        return True
    # Implementation...
    return True

def execute_automation_actions(obj, actions):
    """
    Executes JSON-based actions (e.g., assign to team, update field).
    """
    for action in actions:
        action_type = action.get('type')
        if action_type == 'SET_FIELD':
            field = action.get('field')
            value = action.get('value')
            setattr(obj, field, value)
            obj.save(update_fields=[field])
        elif action_type == 'ASSIGN_TEAM':
            team_id = action.get('team_id')
            obj.assignment_group_id = team_id
            obj.save(update_fields=['assignment_group_id'])
        # Add more action types as needed (NOTIFY, WEBHOOK, etc.)
