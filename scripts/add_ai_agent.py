import sys
import os
import django

# Ensure project root is in path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.accounts.models import User
from apps.teams.models import Team, TeamMember
from apps.organizations.models import Organization

def add_ai_agent_to_teams():
    print("Integrating AI Agent into Technical Teams...")
    
    org = Organization.objects.first()
    if not org:
        print("No organization found.")
        return

    # 1. Get or Create AI Agent User
    ai_agent, created = User.objects.get_or_create(
        email='ai.agent@argus.io',
        defaults={
            "first_name": "AI",
            "last_name": "Agent",
            "username": "ai.agent@argus.io",
            "organization": org,
            "is_active": True
        }
    )
    
    if created:
        ai_agent.set_password("Argus@123")
        ai_agent.save()
        print("Created AI Agent user.")
    else:
        print("AI Agent user already exists.")

    # 2. Add to all specified teams
    team_names = ["Networking Team", "Software Team", "DevOps Team"]
    teams = Team.objects.filter(name__in=team_names)
    
    for team in teams:
        membership, m_created = TeamMember.objects.get_or_create(
            team=team,
            user=ai_agent,
            defaults={"role": "MEMBER"}
        )
        if m_created:
            print(f"Added AI Agent to {team.name}")
        else:
            print(f"AI Agent already a member of {team.name}")

    print("AI Agent Integration Complete!")

if __name__ == "__main__":
    add_ai_agent_to_teams()
