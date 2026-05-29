from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.teams.models import Team, TeamMember


class TeamListScopeTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Team Org A", slug="team-org-a")
        self.org_b = Organization.objects.create(name="Team Org B", slug="team-org-b")
        self.admin = User.objects.create_user(
            username="team-admin",
            email="team-admin@example.com",
            password="pass",
            is_superuser=True,
        )
        self.org_a_team = Team.objects.create(
            name="Client Support",
            description="Client support resolver group",
            organization=self.org_a,
        )
        self.org_b_team = Team.objects.create(
            name="Other Client Support",
            description="Other client support resolver group",
            organization=self.org_b,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _team_names(self, response):
        self.assertEqual(response.status_code, 200)
        return {team["name"] for team in response.data["data"]}

    def test_internal_user_without_org_sees_only_global_teams(self):
        response = self.client.get("/api/v1/teams/")

        self.assertEqual(self._team_names(response), {"Infra Team", "DevOps Team", "Software Team"})
        self.assertEqual(response.data["pagination"]["total"], 3)

    def test_internal_user_with_org_filter_sees_global_and_selected_org_teams(self):
        response = self.client.get(f"/api/v1/teams/?organization_id={self.org_a.id}")

        self.assertEqual(
            self._team_names(response),
            {"Infra Team", "DevOps Team", "Software Team", "Client Support"},
        )
        self.assertEqual(response.data["pagination"]["total"], 4)

    def test_org_filtered_global_team_keeps_internal_admin_members(self):
        infra_team = Team.objects.get(name="Infra Team", organization__isnull=True)
        TeamMember.objects.create(team=infra_team, user=self.admin)

        response = self.client.get(f"/api/v1/teams/?organization_id={self.org_a.id}")

        self.assertEqual(response.status_code, 200, response.data)
        infra_payload = next(team for team in response.data["data"] if team["name"] == "Infra Team")
        member_emails = {member["user"]["email"] for member in infra_payload["members"]}
        self.assertIn(self.admin.email, member_emails)
        admin_member = next(member for member in infra_payload["members"] if member["user"]["email"] == self.admin.email)
        self.assertTrue(admin_member["isAssignable"])
