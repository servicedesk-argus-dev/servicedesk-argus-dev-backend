from io import StringIO

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from .models import AssetRelationship, AssetSite, ConfigurationItem


User = get_user_model()


class AssetParityApiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="CMDB Org", slug="cmdb-org")
        self.user = User.objects.create_user(
            username="cmdb-admin",
            email="cmdb@example.com",
            password="testpass123",
            organization=self.org,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))

    def test_asset_list_bootstraps_linkedeye_style_seed(self):
        response = self.client.get("/api/v1/assets/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertGreaterEqual(body["pagination"]["total"], 10)
        self.assertTrue(AssetSite.objects.filter(organization=self.org, slug="production").exists())
        self.assertTrue(ConfigurationItem.objects.filter(organization=self.org, type=ConfigurationItem.Type.SWITCH).exists())
        self.assertTrue(ConfigurationItem.objects.filter(organization=self.org, type=ConfigurationItem.Type.DATABASE).exists())

    def test_create_asset_accepts_frontend_camel_case_payload(self):
        payload = {
            "name": "edge-fw-01",
            "type": "FIREWALL",
            "status": "LIVE",
            "ipAddress": "10.20.0.1",
            "managementIpAddress": "10.20.0.2",
            "monitoringEnabled": True,
            "serviceName": "Edge Firewall",
        }

        response = self.client.post("/api/v1/assets/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["type"], "FIREWALL")
        self.assertEqual(data["ip_address"], "10.20.0.1")
        self.assertEqual(data["management_ip_address"], "10.20.0.2")

    def test_discovery_scan_and_onboard_creates_ci(self):
        scan = self.client.post(
            "/api/v1/assets/autodiscover/scan/",
            {"from_ip": "10.30.0.10", "to_ip": "10.30.0.10", "asset_type": "SERVER"},
            format="json",
        )
        self.assertEqual(scan.status_code, 201)
        discovery_id = scan.json()["data"][0]["id"]

        onboard = self.client.post(
            "/api/v1/assets/onboard/",
            {"discovery_result": discovery_id, "serviceName": "Discovered Service"},
            format="json",
        )

        self.assertEqual(onboard.status_code, 201)
        data = onboard.json()["data"]
        self.assertEqual(data["asset"]["ip_address"], "10.30.0.10")
        self.assertEqual(data["onboarding"]["status"], "ONBOARDED")
        self.assertEqual(scan.json()["data"][0]["discovered_data"]["source"], "tcp_probe")

    def test_relationships_feed_topology(self):
        site = AssetSite.objects.create(organization=self.org, name="Production", slug="prod")
        source = ConfigurationItem.objects.create(
            organization=self.org,
            site=site,
            name="app-01",
            type=ConfigurationItem.Type.SERVER,
        )
        target = ConfigurationItem.objects.create(
            organization=self.org,
            site=site,
            name="db-01",
            type=ConfigurationItem.Type.DATABASE,
        )

        response = self.client.post(
            f"/api/v1/assets/{source.id}/relationships/",
            {"target_ci": str(target.id), "relationship_type": "DEPENDS_ON", "label": "uses"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(AssetRelationship.objects.count(), 1)

        topology = self.client.get("/api/v1/assets/topology/")
        self.assertEqual(topology.status_code, 200)
        data = topology.json()["data"]
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["edges"]), 1)

    def test_live_metrics_endpoint_returns_realtime_shape(self):
        asset = ConfigurationItem.objects.create(
            organization=self.org,
            name="live-app-01",
            type=ConfigurationItem.Type.SERVER,
            ip_address="127.0.0.1",
            monitoring_enabled=True,
        )

        response = self.client.get(f"/api/v1/assets/{asset.id}/live-metrics/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn(data["liveStatus"], ["healthy", "warning", "critical"])
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        self.assertIn("interfaces", data)
        self.assertIn("probes", data)

    def test_prometheus_config_endpoint_uses_cmdb_targets(self):
        asset = ConfigurationItem.objects.create(
            organization=self.org,
            name="node-exp-01",
            type=ConfigurationItem.Type.SERVER,
            ip_address="10.40.0.10",
            prometheus_job="node",
            monitoring_enabled=True,
        )

        response = self.client.get("/api/v1/assets/prometheus/config/")

        self.assertEqual(response.status_code, 200)
        content = response.json()["data"]["content"]
        self.assertIn("scrape_configs:", content)
        self.assertIn("job_name: 'node'", content)
        self.assertIn("10.40.0.10:9100", content)

    def test_seed_asset_inventory_command_is_idempotent(self):
        out = StringIO()

        call_command("seed_asset_inventory", "--org", self.org.slug, stdout=out)
        first_count = ConfigurationItem.objects.filter(organization=self.org).count()
        self.assertGreaterEqual(first_count, 10)

        call_command("seed_asset_inventory", "--org", self.org.slug, stdout=out)
        second_count = ConfigurationItem.objects.filter(organization=self.org).count()

        self.assertEqual(first_count, second_count)
