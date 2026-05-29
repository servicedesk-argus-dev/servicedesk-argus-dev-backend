import logging
from django.utils import timezone
from django.db.models import Q
from .models import AssignmentRule, CategoryGroupMapping, UserSkill, SkillRequirement, RoundRobinCounter
from apps.teams.models import Team, TeamMember
from apps.accounts.models import User
from apps.incidents.models import Incident

logger = logging.getLogger(__name__)


def resolve_assignment(incident):
    """
    Master entry point. Returns (group, individual) to assign.
    """
    logger.info(f"Resolving assignment for incident {incident.number}")
    
    # 1. Resolve Group
    group = _resolve_group(incident)
    if not group:
        logger.warning(f"Could not resolve group for incident {incident.number}")
        return None, None
    
    # 2. Resolve Individual within the group
    individual = _resolve_individual(incident, group)
    
    return group, individual


def _resolve_group(incident):
    """
    Priority: CI support_group -> Assignment Rules -> Category Mapping fallback
    """
    # Layer 1: CI-Based Routing
    if incident.config_item and incident.config_item.support_group:
        logger.info(f"Resolved group via CI support group: {incident.config_item.support_group.name}")
        return incident.config_item.support_group
    
    # Layer 2: Assignment Rules (ordered)
    rules = AssignmentRule.objects.filter(
        organization=incident.organization,
        is_active=True
    ).order_by('order')
    
    for rule in rules:
        if _evaluate_rule_conditions(incident, rule.conditions):
            logger.info(f"Resolved group via rule: {rule.name}")
            return rule.target_group
            
    # Layer 3: Category Mapping fallback
    mapping = CategoryGroupMapping.objects.filter(
        organization=incident.organization,
        category=incident.category,
        subcategory=incident.subcategory
    ).first()
    
    if not mapping and incident.subcategory:
        # Try category-only mapping
        mapping = CategoryGroupMapping.objects.filter(
            organization=incident.organization,
            category=incident.category,
            subcategory__isnull=True
        ).first()
        
    if mapping:
        logger.info(f"Resolved group via category mapping: {mapping.team.name}")
        return mapping.team
        
    return None


def _resolve_individual(incident, team):
    """
    Priority: On-Call -> Skill-Match -> Round-Robin
    """
    # 1. On-Call Integration (Simplified for now - using TeamLead or first member as proxy if no complex schedule)
    # In a full implementation, we'd check against actual cmn_rota/schedule
    on_call_user = _find_oncall_user(team)
    if on_call_user:
        logger.info(f"Resolved individual via on-call: {on_call_user.email}")
        return on_call_user
        
    # 2. Skill-Based Matching
    skilled_user = _find_skilled_user(team, incident)
    if skilled_user:
        logger.info(f"Resolved individual via skill matching: {skilled_user.email}")
        return skilled_user
        
    # 3. Round-Robin fallback
    rr_user = _round_robin_user(team, incident.organization)
    if rr_user:
        logger.info(f"Resolved individual via round-robin: {rr_user.email}")
        return rr_user
        
    return None


def _evaluate_rule_conditions(incident, conditions):
    """
    Evaluates JSON conditions against incident fields.
    Conditions schema: {"match": "ALL"|"ANY", "rules": [{"field": "...", "operator": "...", "value": "..."}]}
    """
    match_type = conditions.get("match", "ALL")
    rules = conditions.get("rules", [])
    
    if not rules:
        return False
        
    results = []
    for rule in rules:
        field = rule.get("field")
        operator = rule.get("operator")
        expected_value = rule.get("value")
        
        actual_value = getattr(incident, field, None)
        if hasattr(actual_value, 'id'): # Handle FKs
             actual_value = str(actual_value.id)
        
        if operator == "equals":
            results.append(str(actual_value) == str(expected_value))
        elif operator == "contains":
            results.append(str(expected_value).lower() in str(actual_value).lower())
        elif operator == "in":
            results.append(str(actual_value) in expected_value)
        else:
            results.append(False)
            
    if match_type == "ALL":
        return all(results)
    else:
        return any(results)


def _find_oncall_user(team):
    """
    Placeholder for on-call lookup.
    """
    # In production, this would query a schedule table
    # For now, return the team manager if they are active
    if team.manager and team.manager.is_active:
        return team.manager
    return None


def _find_skilled_user(team, incident):
    """
    Match incident category skills against team member skills.
    """
    requirements = SkillRequirement.objects.filter(
        organization=incident.organization,
        category=incident.category,
        subcategory=incident.subcategory
    )
    
    if not requirements.exists() and incident.subcategory:
        requirements = SkillRequirement.objects.filter(
            organization=incident.organization,
            category=incident.category,
            subcategory__isnull=True
        )
        
    if not requirements.exists():
        return None
        
    # Get all team members
    member_ids = TeamMember.objects.filter(team=team).values_list('user_id', flat=True)
    
    # Find users who meet all requirements
    eligible_users = User.objects.filter(id__in=member_ids, is_active=True)
    
    for req in requirements:
        eligible_users = eligible_users.filter(
            skills__skill_name=req.skill_name,
            skills__proficiency__gte=req.min_proficiency
        )
        
    return eligible_users.first()


def _round_robin_user(team, organization):
    """
    Return next eligible member using a client-scoped round-robin counter.

    Teams can be global resolver teams with no organization. The counter still
    needs to be scoped to the incident's client organization so one client's
    routing does not affect another client's rotation.
    """
    if organization is None:
        logger.warning("Round-robin skipped for team %s because incident has no organization", team.id)
        return None

    counter, created = RoundRobinCounter.objects.get_or_create(
        team=team,
        organization=organization,
    )
    
    members = TeamMember.objects.filter(
        team=team,
        is_assignable=True,
        user__is_active=True,
        user__is_active_member=True,
    ).order_by('joined_at')
    if not members.exists():
        return None
        
    if not counter.last_assigned_user:
        next_member = members.first()
    else:
        # Find index of last assigned user
        last_user_id = counter.last_assigned_user_id
        member_list = list(members)
        try:
            current_index = next(i for i, m in enumerate(member_list) if m.user_id == last_user_id)
            next_index = (current_index + 1) % len(member_list)
            next_member = member_list[next_index]
        except (StopIteration, ValueError):
            next_member = members.first()
            
    # Update counter
    counter.last_assigned_user = next_member.user
    counter.save()
    
    return next_member.user
