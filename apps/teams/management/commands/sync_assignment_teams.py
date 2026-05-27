from django.core.management.base import BaseCommand

from apps.assignments.models import CategoryGroupMapping
from apps.organizations.models import Organization
from apps.teams.models import Team


CATEGORY_MAPPINGS = {
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


class Command(BaseCommand):
    help = (
        "Sync default category mappings to existing assignment teams. "
        "This command does not create/delete teams or users."
    )

    def handle(self, *args, **options):
        orgs = Organization.objects.all().order_by("name")
        if not orgs.exists():
            self.stdout.write(self.style.WARNING("No organizations found."))
            return

        for org in orgs:
            self.stdout.write(f"Syncing category mappings for {org.name}")
            for category, team_name in CATEGORY_MAPPINGS.items():
                team = (
                    Team.objects.filter(name=team_name, is_active=True, organization=org).first()
                    or Team.objects.filter(name=team_name, is_active=True, organization__isnull=True).first()
                )
                if team is None:
                    self.stdout.write(self.style.WARNING(f"Skipping {category}: {team_name} is not configured."))
                    continue
                CategoryGroupMapping.objects.update_or_create(
                    organization=org,
                    category=category,
                    subcategory=None,
                    defaults={"team": team},
                )

        self.stdout.write(self.style.SUCCESS("Category mappings synced."))
