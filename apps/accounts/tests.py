from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.common.permissions import Roles, user_has_permission
from apps.organizations.models import Organization
from apps.teams.models import Team
from .models import Role


User = get_user_model()


class ManagedAccountCreationTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="E2E Client", slug="e2e-client")
        self.team = Team.objects.create(name="Infra Team", description="Resolver team")
        self.admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminPass123!",
        )
        self.admin.roles.add(Role.objects.create(name=Roles.SUPER_ADMIN))
        self.client.force_authenticate(self.admin)

    def test_admin_creates_client_user_with_temporary_password(self):
        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "client@example.com",
                "password": "TempPass123!",
                "role_name": "Client User",
                "organization_id": str(self.org.id),
                "must_change_password": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="client@example.com")
        self.assertEqual(user.organization_id, self.org.id)
        self.assertEqual(user.role_names, [Roles.CLIENT_USER])
        self.assertTrue(user.must_change_password)
        self.assertFalse(user.team_memberships.exists())

    def test_admin_creates_engineer_from_keycloak_token_role_and_team(self):
        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "engineer@example.com",
                "password": "TempPass123!",
                "role_name": "ENGINEER",
                "team_ids": [str(self.team.id)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="engineer@example.com")
        self.assertEqual(user.role_names, [Roles.ENGINEER])
        self.assertIsNone(user.organization_id)
        self.assertEqual(list(user.team_memberships.values_list("team__name", flat=True)), ["Infra Team"])
        self.assertTrue(user_has_permission(user, "incident:update"))

    def test_client_scoped_roles_require_client_organization(self):
        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "viewer@example.com",
                "password": "TempPass123!",
                "role_name": "Viewer",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("organization_id", response.data)


class RoleCompatibilityTests(APITestCase):
    def test_keycloak_token_role_name_gets_default_permissions(self):
        user = User.objects.create_user(
            username="kc-engineer@example.com",
            email="kc-engineer@example.com",
            password="TempPass123!",
        )
        user.roles.add(Role.objects.create(name="ENGINEER"))

        self.assertTrue(user_has_permission(user, "incident:update"))
        self.assertTrue(user.has_role(Roles.ENGINEER))
