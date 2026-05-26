from datetime import timedelta

from django.test import TestCase

from apps.organizations.models import Organization

from .models import SLADefinition
from .services import derive_incident_priority, ensure_default_definitions, get_sla_targets


class SLADefinitionServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Argus Test", slug="argus-test")

    def test_default_incident_definitions_are_created(self):
        ensure_default_definitions(self.organization)

        priorities = set(
            SLADefinition.objects.filter(organization=self.organization).values_list("priority", flat=True)
        )

        self.assertEqual(priorities, {"P1", "P2", "P3", "P4"})

    def test_custom_definition_drives_targets(self):
        ensure_default_definitions(self.organization)
        SLADefinition.objects.filter(organization=self.organization, priority="P1").update(
            response_time_minutes=7,
            resolution_time_minutes=90,
        )

        response_target, resolution_target = get_sla_targets(self.organization, "P1")

        self.assertEqual(response_target, timedelta(minutes=7))
        self.assertEqual(resolution_target, timedelta(minutes=90))

    def test_priority_matrix_matches_service_desk_impact_and_urgency(self):
        self.assertEqual(derive_incident_priority("ENTERPRISE", "HIGH"), "P1")
        self.assertEqual(derive_incident_priority("TEAM", "MEDIUM"), "P3")
        self.assertEqual(derive_incident_priority("INDIVIDUAL", "LOW"), "P4")
