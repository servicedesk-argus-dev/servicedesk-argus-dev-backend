import sys
import os
import django
import uuid

# Ensure project root is in path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.accounts.models import User
from apps.teams.models import Team, TeamMember
from apps.organizations.models import Organization
from apps.assignments.models import CategoryGroupMapping, AssignmentRule, UserSkill, SkillRequirement
from apps.incidents.models import Incident

def bootstrap_enterprise_assignment():
    print("Bootstrapping Enterprise Assignment Logic...")
    
    org = Organization.objects.first()
    if not org:
        print("No organization found. Please run seed script first.")
        return

    # 1. Ensure we have a few key teams
    it_servicedesk, _ = Team.objects.get_or_create(
        name="IT Service Desk",
        organization=org,
        defaults={"description": "First level support"}
    )
    network_team, _ = Team.objects.get_or_create(
        name="Network Team",
        organization=org,
        defaults={"description": "Network infrastructure support"}
    )
    db_team, _ = Team.objects.get_or_create(
        name="Database Team",
        organization=org,
        defaults={"description": "Database administration support"}
    )

    # 2. Setup Category -> Group Mappings
    mappings = [
        ("Software", None, it_servicedesk),
        ("Hardware", None, it_servicedesk),
        ("Network", None, network_team),
        ("Database", None, db_team),
        ("Security", None, network_team),
    ]
    
    for cat, sub, team in mappings:
        CategoryGroupMapping.objects.get_or_create(
            organization=org,
            category=cat,
            subcategory=sub,
            defaults={"team": team}
        )
    print("Category mappings established.")

    # 3. Setup an Assignment Rule for \"Urgent Database Issues\"
    AssignmentRule.objects.get_or_create(
        name="Urgent Database Issues",
        organization=org,
        defaults={
            "order": 10,
            "target_group": db_team,
            "conditions": {
                "match": "ALL",
                "rules": [
                    {"field": "category", "operator": "equals", "value": "Database"},
                    {"field": "urgency", "operator": "equals", "value": "CRITICAL"}
                ]
            }
        }
    )
    print("Assignment rules configured.")

    # 4. Fix 'Monitoring System' issue - Ensure it's not the default if user exists
    admin_user = User.objects.filter(is_superuser=True).first()
    if admin_user:
        Incident.objects.filter(requested_by__isnull=True).update(requested_by=admin_user)
        print(f"Updated existing incidents to be requested by: {admin_user.email}")

    print("Enterprise Assignment Bootstrap Complete!")

if __name__ == "__main__":
    bootstrap_enterprise_assignment()
