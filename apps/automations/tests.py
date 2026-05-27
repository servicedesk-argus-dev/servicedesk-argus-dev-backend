from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization
from apps.incidents.models import Incident
from .models import AutomationRule
from .engine import process_automations

User = get_user_model()

class AutomationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123",
            organization=self.org
        )
        
    def test_create_rule(self):
        rule = AutomationRule.objects.create(
            name="Set Priority to P1",
            organization=self.org,
            trigger=AutomationRule.Trigger.ON_CREATE,
            target_model="incidents.Incident",
            actions=[{"type": "SET_FIELD", "field": "priority", "value": "P1"}]
        )
        self.assertEqual(rule.name, "Set Priority to P1")

    def test_automation_engine_execution(self):
        # Create a rule to auto-resolve incidents with a specific description
        rule = AutomationRule.objects.create(
            name="Auto Resolve Test",
            organization=self.org,
            trigger=AutomationRule.Trigger.ON_CREATE,
            target_model="incidents.Incident",
            conditions=[{"field": "description", "operator": "contains", "value": "AUTO_RESOLVE"}],
            actions=[{"type": "SET_FIELD", "field": "state", "value": "RESOLVED"}]
        )
        
        # This is a bit tricky to test with signals unless we ensure signals are connected
        # For now, we test the engine function directly
        incident = Incident.objects.create(
            short_description="Test Incident",
            description="This is an AUTO_RESOLVE incident",
            organization=self.org,
            created_by=self.user
        )
        
        # Run engine
        process_automations(incident, AutomationRule.Trigger.ON_CREATE)
        
        # Refresh from DB
        incident.refresh_from_db()
        self.assertEqual(incident.state, "RESOLVED")
