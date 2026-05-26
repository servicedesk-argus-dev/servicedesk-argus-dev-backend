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

def setup_specific_teams():
    print("Initializing Enterprise Team Membership...")
    
    org = Organization.objects.first()
    if not org:
        print("No organization found.")
        return

    # Data structure for teams and members
    teams_data = {
        "Infra Team": ["Devendra Reddy", "Edukondalu", "Siva", "Udhayakumar"],
        "DevOps Team": ["Rajkumar-Madhu", "Hoysala Bisa"],
        "Software Team": ["Vediyappan M", "Rajkumar-Ashokan"],
    }

    for team_name, member_names in teams_data.items():
        # 1. Get or Create Team
        team, created = Team.objects.get_or_create(
            name=team_name,
            organization=org,
            defaults={"description": f"Dedicated team for {team_name}"}
        )
        if created:
            print(f"Created Team: {team_name}")
        else:
            print(f"Using existing Team: {team_name}")

        for full_name in member_names:
            # Generate a simple email from name
            email_prefix = full_name.lower().replace(" ", ".")
            email = f"{email_prefix}@argus.io"
            
            # 2. Get or Create User
            user, u_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": full_name.split(" ")[0],
                    "last_name": " ".join(full_name.split(" ")[1:]) if " " in full_name else "",
                    "username": email,
                    "organization": org,
                    "is_active": True
                }
            )
            
            if u_created:
                user.set_password("Argus@123") # Default password
                user.save()
                print(f"  Created User: {full_name} ({email})")
            
            # 3. Add to Team
            membership, m_created = TeamMember.objects.get_or_create(
                team=team,
                user=user,
                defaults={"role": "MEMBER"}
            )
            if m_created:
                print(f"  Added {full_name} to {team_name}")
            else:
                print(f"  {full_name} already in {team_name}")

    print("Enterprise Team Setup Complete!")

if __name__ == "__main__":
    setup_specific_teams()
