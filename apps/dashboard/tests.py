from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.dashboard.views import _dashboard_payload
from apps.incidents.models import Incident
from apps.organizations.models import Organization


class DashboardIncidentStatsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Dashboard Org", slug="dashboard-org")
        self.user = User.objects.create_user(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="pass",
            organization=self.org,
        )

    def _incident(self, number, *, source, state=Incident.State.NEW):
        return Incident.objects.create(
            number=number,
            short_description=f"{number} test",
            description="Dashboard count test",
            source=source,
            state=state,
            priority=Incident.Priority.P2,
            impact=Incident.Impact.TEAM,
            urgency=Incident.Urgency.HIGH,
            created_by=self.user,
            organization=self.org,
        )

    def test_dashboard_counts_manual_and_webhook_incidents(self):
        self._incident("INC-DASH-001", source=Incident.Source.MANUAL)
        self._incident("INC-DASH-002", source=Incident.Source.API)
        self._incident("INC-DASH-003", source=Incident.Source.PROMETHEUS, state=Incident.State.RESOLVED)

        stats = _dashboard_payload(self.org.id)["incidents"]

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["manual"], 1)
        self.assertEqual(stats["automated"], 2)
        self.assertEqual(stats["open"], 2)
        self.assertEqual(stats["by_source"][Incident.Source.API], 1)

    def test_dashboard_all_org_scope_counts_api_incidents(self):
        self._incident("INC-DASH-004", source=Incident.Source.API)
        other_org = Organization.objects.create(name="Other Dashboard Org", slug="other-dashboard-org")
        other_user = User.objects.create_user(
            username="other-dashboard-admin",
            email="other-dashboard-admin@example.com",
            password="pass",
            organization=other_org,
        )
        Incident.objects.create(
            number="INC-DASH-005",
            short_description="Other org API incident",
            source=Incident.Source.API,
            state=Incident.State.NEW,
            priority=Incident.Priority.P3,
            impact=Incident.Impact.TEAM,
            urgency=Incident.Urgency.MEDIUM,
            created_by=other_user,
            organization=other_org,
            resolved_at=timezone.now() - timedelta(hours=1),
        )

        stats = _dashboard_payload(None)["incidents"]

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["automated"], 2)
