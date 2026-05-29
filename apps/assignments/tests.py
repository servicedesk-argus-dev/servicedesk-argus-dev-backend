from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.incidents.models import Incident
from apps.organizations.models import Organization
from apps.teams.models import Team, TeamMember

from .models import CategoryGroupMapping, RoundRobinCounter
from .services import resolve_assignment


User = get_user_model()


class AssignmentEngineTests(TestCase):
    def test_global_team_round_robin_counter_is_scoped_to_incident_organization(self):
        organization = Organization.objects.create(name="E2E Client", slug="e2e-client")
        team = Team.objects.create(name="Infra Team", organization=None, is_active=True)
        user = User.objects.create_user(
            username="engineer@example.com",
            email="engineer@example.com",
            password="TempPass123!",
        )
        TeamMember.objects.create(team=team, user=user, is_assignable=True)
        CategoryGroupMapping.objects.create(
            organization=organization,
            category="Network",
            subcategory="Firewall",
            team=team,
        )

        incident = Incident(
            organization=organization,
            category="Network",
            subcategory="Firewall",
            impact=Incident.Impact.TEAM,
            urgency=Incident.Urgency.MEDIUM,
        )

        group, individual = resolve_assignment(incident)

        self.assertEqual(group, team)
        self.assertEqual(individual, user)
        counter = RoundRobinCounter.objects.get(team=team, organization=organization)
        self.assertEqual(counter.last_assigned_user, user)
