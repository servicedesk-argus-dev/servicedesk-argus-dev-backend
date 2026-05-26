from django.utils import timezone
from .models import Change, MaintenanceWindow, ChangeCI
from django.db.models import Q

def detect_conflicts(change: Change):
    """
    Detects scheduling conflicts for a Change request.
    Returns a list of conflict objects: {"type": "BLACKOUT"|"CHANGE_OVERLAP", "message": "...", "related_id": "..."}
    """
    conflicts = []
    
    if not change.planned_start_date or not change.planned_end_date:
        return conflicts

    # 1. Check for Blackout Windows
    # A blackout window conflicts if it overlaps with the change and has no CI/Group scope 
    # OR if it matches the change's CIs/Groups.
    blackouts = MaintenanceWindow.objects.filter(
        organization=change.organization,
        type=MaintenanceWindow.Type.BLACKOUT,
        start_date__lt=change.planned_end_date,
        end_date__gt=change.planned_start_date
    )
    
    for blackout in blackouts:
        # If blackout is global (no CIs/Groups), it's a conflict
        if not blackout.affected_cis.exists() and not blackout.affected_groups.exists():
            conflicts.append({
                "type": "BLACKOUT",
                "message": f"Change overlaps with Global Blackout Period: {blackout.name}",
                "related_id": str(blackout.id)
            })
            continue
            
        # Check if any of the change's affected CIs are in the blackout
        change_cis = set(change.affected_cis.values_list('config_item_id', flat=True))
        blackout_cis = set(blackout.affected_cis.values_list('id', flat=True))
        
        if change_cis.intersection(blackout_cis):
            conflicts.append({
                "type": "BLACKOUT",
                "message": f"Change affects CIs that are restricted by Blackout: {blackout.name}",
                "related_id": str(blackout.id)
            })
            
    # 2. Check for overlapping Changes on the same CIs
    overlapping_changes = Change.objects.filter(
        organization=change.organization,
        planned_start_date__lt=change.planned_end_date,
        planned_end_date__gt=change.planned_start_date
    ).exclude(id=change.id).exclude(state__in=[Change.State.CLOSED, Change.State.CANCELLED])
    
    # Efficiently find CI overlaps
    change_cis = set(change.affected_cis.values_list('config_item_id', flat=True))
    for other_change in overlapping_changes:
        other_cis = set(other_change.affected_cis.values_list('config_item_id', flat=True))
        if change_cis.intersection(other_cis):
            conflicts.append({
                "type": "CHANGE_OVERLAP",
                "message": f"Scheduling conflict with {other_change.number}: Both affect same CIs.",
                "related_id": str(other_change.id)
            })
            
    return conflicts

def calculate_risk_score(assessment_data: list):
    """
    Calculates a risk score based on a list of answered questions.
    Each item in data: {"question": "...", "answer": "Yes"|"No", "weight": 10}
    """
    score = 0
    for item in assessment_data:
        # Simple logic: "Yes" answers add weight (meaning higher risk)
        # In a real system, this would be more complex.
        if item.get("answer") == "Yes":
            score += item.get("weight", 0)
    return score
