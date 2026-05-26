import os
import sys
import django

# Ensure project root is in path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.accounts.models import User
from apps.teams.models import Team, TeamMember
from apps.organizations.models import Organization
from apps.assignments.models import CategoryGroupMapping

def clean_and_setup():
    print("--- Cleaning and Setting up Enterprise Teams in Default Org ---")
    
    org = Organization.objects.filter(name='Default Organization').first()
    if not org:
        print("Error: Default Organization not found.")
        return

    # 1. Clear existing mappings and teams in this org
    print(f"Deleting existing teams and mappings in {org.name}...")
    CategoryGroupMapping.objects.filter(organization=org).delete()
    Team.objects.filter(organization=org).delete()

    # Data structure for teams and members
    teams_data = {
        "Infra Team": ["Devendra Reddy", "Edukondalu", "Siva", "Udhayakumar"],
        "DevOps Team": ["Rajkumar-Madhu", "Hoysala Bisa"],
        "Software Team": ["Vediyappan M", "Rajkumar-Ashokan"],
    }

    category_mappings = {
        "Network": "Infra Team",
        "Security": "Infra Team",
        "Infrastructure": "Infra Team",
        "Hardware": "Infra Team",
        "Cloud": "DevOps Team",
        "Cloud Infrastructure": "DevOps Team",
        "DevOps": "DevOps Team",
        "Software": "Software Team",
        "Application": "Software Team",
        "Database": "Software Team",
        "Configuration": "Software Team",
    }

    # 2. Sync AI Agent for this Org
    ai_agent_email = f'ai.agent.{org.id}@argus.io'
    ai_agent, _ = User.objects.get_or_create(
        email=ai_agent_email,
        defaults={
            "first_name": "AI",
            "last_name": "Agent",
            "username": ai_agent_email,
            "organization": org,
            "is_active": True
        }
    )
    ai_agent.organization = org
    ai_agent.set_password("Argus@123")
    ai_agent.save()

    # 3. Create Teams and Members
    for team_name, member_names in teams_data.items():
        team = Team.objects.create(
            name=team_name,
            organization=org,
            description=f"Enterprise {team_name} for {org.name}"
        )
        print(f"Created Team: {team_name}")
        
        # Add AI Agent
        TeamMember.objects.create(team=team, user=ai_agent, role="MEMBER")

        for full_name in member_names:
            email_prefix = full_name.lower().replace(" ", ".")
            email = f"{email_prefix}.{org.id}@argus.io"
            
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": full_name.split(" ")[0],
                    "last_name": " ".join(full_name.split(" ")[1:]) if " " in full_name else "",
                    "username": email,
                    "organization": org,
                    "is_active": True
                }
            )
            user.organization = org
            user.save()
            
            TeamMember.objects.create(team=team, user=user, role="MEMBER")
            print(f"  Added {full_name} to {team_name}")
    
    # 4. Setup Category Mappings
    for category, target_team_name in category_mappings.items():
        target_team = Team.objects.filter(name=target_team_name, organization=org).first()
        if target_team:
            CategoryGroupMapping.objects.create(
                category=category,
                organization=org,
                team=target_team
            )

    print("\nSUCCESS: Clean Setup Complete!")

if __name__ == "__main__":
    clean_and_setup()
