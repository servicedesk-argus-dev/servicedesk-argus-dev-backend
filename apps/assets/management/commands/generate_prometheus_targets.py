import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.assets.models import ConfigurationItem


class Command(BaseCommand):
    help = "Generate Prometheus file-SD target files from active monitored configuration items."

    def handle(self, *args, **options):
        output_dir = Path(settings.PROMETHEUS_FILE_SD_PATH)
        output_dir.mkdir(parents=True, exist_ok=True)

        grouped_targets = defaultdict(list)
        skipped = []
        exported = 0

        queryset = (
            ConfigurationItem.all_objects
            .filter(monitoring_enabled=True)
            .exclude(status=ConfigurationItem.Status.DECOMMISSIONED)
            .select_related("organization", "site")
            .order_by("organization__slug", "hostname", "ip_address", "id")
        )

        for ci in queryset:
            host = ci.hostname or (str(ci.ip_address) if ci.ip_address else None)
            if not host:
                skipped.append(str(ci.id))
                continue

            grouped_targets[ci.organization.slug].append(
                {
                    "targets": [f"{host}:9100"],
                    "labels": {
                        "job": ci.prometheus_job or "node",
                        "org": ci.organization.slug,
                        "ci_id": str(ci.id),
                        "hostname": ci.hostname or host,
                        "environment": ci.site.environment if ci.site and ci.site.environment else "",
                    },
                }
            )
            exported += 1

        org_count = 0
        for org_slug, entries in sorted(grouped_targets.items()):
            file_path = output_dir / f"{org_slug}.json"
            payload = sorted(
                entries,
                key=lambda item: (
                    item["labels"]["hostname"],
                    item["labels"]["ci_id"],
                ),
            )
            file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            org_count += 1

        (output_dir / ".last_generated").write_text(
            datetime.now(timezone.utc).isoformat(),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {org_count} orgs, exported {exported} configuration items, skipped {len(skipped)}."
            )
        )
        if skipped:
            self.stdout.write(f"Skipped CI IDs: {', '.join(skipped)}")
