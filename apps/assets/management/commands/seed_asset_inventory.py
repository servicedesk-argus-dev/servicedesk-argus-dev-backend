from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import Organization
from apps.assets.bootstrap import bootstrap_inventory_for_organization


class Command(BaseCommand):
    help = "Seed LinkedEye-style CMDB inventory for an organization."

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True, help="Organization slug")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Also backfill site host defaults used by local realtime integrations.",
        )

    def handle(self, *args, **options):
        slug = options["org"]
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Organization '{slug}' not found.") from exc

        summary = bootstrap_inventory_for_organization(org, force=options["force"])
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded asset inventory for "
                f"{slug}: assets={summary['assets']} "
                f"created={summary['assets_created']} "
                f"updated={summary['assets_updated']} "
                f"teams={summary['teams']} "
                f"relationships={summary['relationships_created']} "
                f"port_connections={summary['port_connections_created']}"
            )
        )
