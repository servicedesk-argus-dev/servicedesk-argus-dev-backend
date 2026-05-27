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

def sync_enterprise_data():
    print("--- Starting Enterprise Data Synchronization ---")
    
    orgs = Organization.objects.all()
    if not orgs.exists():
        print("Error: No organizations found. Run migrations or seed data first.")
        return

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

    for org in orgs:
        print(f"\nProcessing Organization: {org.name}")
        
        # 1. Create/Sync AI Agent for this Org
        ai_agent, _ = User.objects.get_or_create(
            email=f'ai.agent.{org.id}@argus.io' if org.name != "Argus Enterprise" else 'ai.agent@argus.io',
            defaults={
                "first_name": "AI",
                "last_name": "Agent",
                "username": f'ai.agent.{org.id}@argus.io' if org.name != "Argus Enterprise" else 'ai.agent@argus.io',
                "organization": org,
                "is_active": True
            }
        )
        if ai_agent.pk:
            ai_agent.organization = org
            ai_agent.set_password("Argus@123")
            ai_agent.save()

        # 2. Setup Teams and Members
        for team_name, member_names in teams_data.items():
            team, created = Team.objects.get_or_create(
                name=team_name,
                organization=org,
                defaults={"description": f"Enterprise {team_name} for {org.name}"}
            )
            
            # Add AI Agent to every team
            TeamMember.objects.get_or_create(team=team, user=ai_agent, defaults={"role": "MEMBER"})

            for full_name in member_names:
                email_prefix = full_name.lower().replace(" ", ".")
                email = f"{email_prefix}.{org.id}@argus.io" if org.name != "Argus Enterprise" else f"{email_prefix}@argus.io"
                
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
                
                TeamMember.objects.get_or_create(team=team, user=user, defaults={"role": "MEMBER"})
        
        # 3. Setup Category Mappings
        for category, target_team_name in category_mappings.items():
            target_team = Team.objects.filter(name=target_team_name, organization=org).first()
            if target_team:
                CategoryGroupMapping.objects.get_or_create(
                    category=category,
                    organization=org,
                    defaults={"team": target_team}
                )

    print("\nSUCCESS: Enterprise Data Sync Complete for all Organizations!")

if __name__ == "__main__":
    sync_enterprise_data()
