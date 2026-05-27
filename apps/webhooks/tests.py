from django.test import override_settings
from rest_framework.test import APITestCase

from apps.incidents.models import Incident
from apps.organizations.models import Organization


@override_settings(ARGUS_WEBHOOK_API_TOKEN="test-linkedeye-token")
class LinkedEyeIncidentWebhookTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="LinkedEye Org", slug="linkedeye-org")
        self.url = "/api/v1/webhooks/linkedeye/incident/"
        self.auth = {"HTTP_AUTHORIZATION": "Bearer test-linkedeye-token"}

    def _payload(self, **overrides):
        payload = {
            "organization_slug": self.org.slug,
            "source_alert_id": "linkedeye:prod-db:cpu-critical",
            "source_alert_name": "CPU Critical",
            "short_description": "CPU Critical on prod-db",
            "description": "CPU usage crossed 95%.",
            "severity": "critical",
            "state": "NEW",
            "site_name": "Primary DC",
            "host": "prod-db",
        }
        payload.update(overrides)
        return payload

    def test_rejects_missing_token_when_token_is_configured(self):
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Incident.objects.count(), 0)

    def test_new_alert_creates_incident(self):
        response = self.client.post(self.url, self._payload(), format="json", **self.auth)

        self.assertEqual(response.status_code, 201, response.data)
        incident = Incident.objects.get()
        self.assertEqual(incident.organization, self.org)
        self.assertEqual(incident.source, Incident.Source.API)
        self.assertEqual(incident.source_alert_id, "linkedeye:prod-db:cpu-critical")
        self.assertEqual(incident.priority, Incident.Priority.P1)
        self.assertEqual(incident.state, Incident.State.NEW)

    def test_duplicate_new_alert_returns_existing_incident(self):
        first = self.client.post(self.url, self._payload(), format="json", **self.auth)
        second = self.client.post(self.url, self._payload(description="Still firing"), format="json", **self.auth)

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(Incident.objects.count(), 1)
        incident = Incident.objects.get()
        self.assertIn("Still firing", incident.description)
        self.assertEqual(second.data["data"]["action"], "deduplicated")

    def test_resolved_alert_resolves_existing_incident(self):
        created = self.client.post(self.url, self._payload(), format="json", **self.auth)
        self.assertEqual(created.status_code, 201, created.data)

        resolved = self.client.post(
            self.url,
            self._payload(state="RESOLVED", resolution_notes="LinkedEye check recovered."),
            format="json",
            **self.auth,
        )

        self.assertEqual(resolved.status_code, 200, resolved.data)
        incident = Incident.objects.get()
        self.assertEqual(incident.state, Incident.State.RESOLVED)
        self.assertIsNotNone(incident.resolved_at)
        self.assertEqual(incident.resolution_notes, "LinkedEye check recovered.")
        self.assertEqual(incident.work_notes.count(), 1)

        repeated = self.client.post(
            self.url,
            self._payload(state="RESOLVED", resolution_notes="Still recovered."),
            format="json",
            **self.auth,
        )
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data["data"]["action"], "already_resolved")
        self.assertEqual(Incident.objects.get().work_notes.count(), 1)


@override_settings(ARGUS_WEBHOOK_API_TOKEN="")
class LinkedEyeIncidentWebhookNoTokenTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="LinkedEye No Token Org", slug="linkedeye-no-token-org")
        self.url = "/api/v1/webhooks/linkedeye/incident/"

    def test_accepts_internal_webhook_without_authorization_when_no_token_configured(self):
        response = self.client.post(
            self.url,
            {
                "organization_slug": self.org.slug,
                "source_alert_id": "linkedeye:no-token:cpu-critical",
                "short_description": "CPU Critical without auth header",
                "description": "LinkedEye sent this with ARGUS_API_TOKEN empty.",
                "severity": "critical",
                "state": "NEW",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        incident = Incident.objects.get(source_alert_id="linkedeye:no-token:cpu-critical")
        self.assertEqual(incident.source, Incident.Source.API)
        self.assertEqual(incident.organization, self.org)
