from django.core.exceptions import PermissionDenied
from apps.workflows.models import Workflow, WorkflowState, WorkflowTransition

def get_available_transitions(obj, user):
    """
    Returns a list of transitions available for the given object and user.
    """
    from django.contrib.contenttypes.models import ContentType
    content_type = ContentType.objects.get_for_model(obj)
    
    workflow = Workflow.objects.filter(
        organization=obj.organization,
        target_content_type=content_type,
        is_active=True
    ).first()
    
    if not workflow:
        return []
        
    current_state_name = getattr(obj, 'state', None)
    if not current_state_name:
        return []
        
    current_state = WorkflowState.objects.filter(workflow=workflow, name=current_state_name).first()
    if not current_state:
        return []
        
    transitions = WorkflowTransition.objects.filter(from_state=current_state)
    
    available = []
    for t in transitions:
        # Check permissions
        if t.required_permission and not user.roles.filter(permissions__code=t.required_permission).exists():
            if not user.is_superuser:
                continue
        
        # Check conditions (simplistic implementation)
        if evaluate_workflow_conditions(obj, t.conditions):
            available.append(t)
            
    return available

def perform_transition(obj, transition_id, user):
    """
    Performs a workflow transition on an object.
    """
    transition = WorkflowTransition.objects.get(id=transition_id)
    
    # Verify it's a valid transition for the current state
    if obj.state != transition.from_state.name:
        raise ValueError(f"Invalid transition from state {obj.state}")
        
    # Check permissions
    if transition.required_permission and not user.roles.filter(permissions__code=transition.required_permission).exists():
        if not user.is_superuser:
            raise PermissionDenied("You do not have permission to perform this transition.")
            
    # Update object state
    obj.state = transition.to_state.name
    obj.save(update_fields=['state'])
    
    # Record activity/audit log
    from apps.incidents.models import Activity
    from django.contrib.contenttypes.models import ContentType
    
    content_type = ContentType.objects.get_for_model(obj)
    
    Activity.objects.create(
        action="WORKFLOW_TRANSITION",
        description=f"Transitioned from {transition.from_state.name} to {transition.to_state.name} via '{transition.name}'",
        old_value=transition.from_state.name,
        new_value=transition.to_state.name,
        user=user,
        # Logic to link to the specific object
        **{content_type.model: obj}
    )

def evaluate_workflow_conditions(obj, conditions):
    """
    Evaluate JSON-based conditions.
    """
    if not conditions:
        return True
    # Implementation of condition evaluation logic...
    return True
