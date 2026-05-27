from django.core.management.base import BaseCommand

from apps.assets.models import ConfigurationItem
from apps.assets.services import AssetLiveStatusService
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Refresh Redis-backed live status snapshots for monitored CMDB assets."

    def add_arguments(self, parser):
        parser.add_argument("--org", help="Organization slug or UUID")
        parser.add_argument("--asset", help="Configuration item UUID")

    def handle(self, *args, **options):
        queryset = ConfigurationItem.objects.filter(monitoring_enabled=True).prefetch_related(
            "management_endpoints"
        ).select_related("site")

        if options["org"]:
            org = Organization.objects.filter(slug=options["org"]).first() or Organization.objects.filter(id=options["org"]).first()
            if not org:
                self.stderr.write(self.style.ERROR("Organization not found"))
                return
            queryset = queryset.filter(organization=org)

        if options["asset"]:
            queryset = queryset.filter(id=options["asset"])

        count = 0
        for asset in queryset:
            live = AssetLiveStatusService.refresh(asset)
            count += 1
            self.stdout.write(f"{asset.name}: {live['liveStatus']} health={live['healthScore']}")

        self.stdout.write(self.style.SUCCESS(f"Refreshed {count} asset(s)."))
