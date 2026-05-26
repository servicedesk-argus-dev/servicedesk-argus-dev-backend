from django.core.management.base import BaseCommand

from apps.assets.services import PrometheusConfigService
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Generate Prometheus scrape configuration from CMDB monitoring endpoints."

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True, help="Organization slug or UUID")
        parser.add_argument("--print", action="store_true", help="Print generated YAML instead of writing prom-conf file")

    def handle(self, *args, **options):
        org = Organization.objects.filter(slug=options["org"]).first() or Organization.objects.filter(id=options["org"]).first()
        if not org:
            self.stderr.write(self.style.ERROR("Organization not found"))
            return

        if options["print"]:
            self.stdout.write(PrometheusConfigService.generate(str(org.id)))
            return

        path, _content = PrometheusConfigService.write(str(org.id))
        self.stdout.write(self.style.SUCCESS(f"Generated {path}"))
