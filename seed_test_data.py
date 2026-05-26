import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.accounts.models import Role, User
from apps.organizations.models import Organization
from apps.teams.models import Team

def seed():
    # 1. Org
    org, _ = Organization.objects.get_or_create(
        name="Argus Enterprise",
        defaults={"slug": "argus-ent"}
    )
    
    # 2. Roles
    role_names = ["Super Admin", "Org Admin", "Manager", "Engineer", "Operator", "Viewer"]
    roles = {}
    for name in role_names:
        role, _ = Role.objects.get_or_create(name=name)
        roles[name] = role
        
    # 3. User
    user, created = User.objects.get_or_create(
        username="admin@argus.com",
        defaults={
            "email": "admin@argus.com",
            "first_name": "Argus",
            "last_name": "Admin",
            "organization": org,
            "is_staff": True,
            "is_superuser": True
        }
    )
    if created:
        user.set_password("admin123456")
        user.save()
    
    user.roles.add(roles["Super Admin"])
    
    # 4. Team
    team, _ = Team.objects.get_or_create(
        name="IT Operations",
        organization=org,
        defaults={"manager": user}
    )
    
    print("Seeding complete.")

if __name__ == "__main__":
    seed()
