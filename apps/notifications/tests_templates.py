from django.test import TestCase
from apps.organizations.models import Organization
from .models import NotificationTemplate

class NotificationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")

    def test_create_template(self):
        template = NotificationTemplate.objects.create(
            name="New Incident Notification",
            organization=self.org,
            channel="EMAIL",
            subject_template="New Incident: {{ incident.number }}",
            body_template="An incident has been created: {{ incident.short_description }}",
            type="INCIDENT"
        )
        self.assertEqual(template.channel, "EMAIL")
        self.assertIn("{{ incident.number }}", template.subject_template)

    def test_template_filtering(self):
        NotificationTemplate.objects.create(
            name="T1", organization=self.org, channel="EMAIL", type="SYSTEM"
        )
        self.assertEqual(NotificationTemplate.objects.filter(organization=self.org).count(), 1)
