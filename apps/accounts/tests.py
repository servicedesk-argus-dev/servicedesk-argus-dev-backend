from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.common.permissions import Roles, user_has_permission
from apps.organizations.models import Organization
from apps.teams.models import Team
from .models import Permission, Role


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

    def test_super_admin_creates_admin_account(self):
        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "admin2@example.com",
                "password": "TempPass123!",
                "role_name": "Org Admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="admin2@example.com")
        self.assertEqual(user.role_names, [Roles.ORG_ADMIN])
        self.assertTrue(user_has_permission(user, "user:manage"))
        self.assertTrue(user_has_permission(user, "client:manage"))
        self.assertFalse(user_has_permission(user, "*:*"))

    def test_super_admin_creates_admin_account_with_resolver_team(self):
        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "admin-resolver@example.com",
                "password": "TempPass123!",
                "role_name": "Org Admin",
                "team_ids": [str(self.team.id)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="admin-resolver@example.com")
        self.assertEqual(user.role_names, [Roles.ORG_ADMIN])
        self.assertEqual(list(user.team_memberships.values_list("team__name", flat=True)), ["Infra Team"])
        self.assertTrue(user.team_memberships.get(team=self.team).is_assignable)
        self.assertTrue(user_has_permission(user, "user:manage"))
        self.assertTrue(user_has_permission(user, "incident:update"))

    def test_admin_alias_creates_org_admin_account(self):
        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "admin-alias@example.com",
                "password": "TempPass123!",
                "role_name": "Admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="admin-alias@example.com")
        self.assertEqual(user.role_names, [Roles.ORG_ADMIN])

    def test_manager_cannot_create_admin_account(self):
        manager = User.objects.create_user(
            username="manager@example.com",
            email="manager@example.com",
            password="ManagerPass123!",
        )
        manager.roles.add(Role.objects.create(name=Roles.MANAGER))
        self.client.force_authenticate(manager)

        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "blocked-admin@example.com",
                "password": "TempPass123!",
                "role_name": "Org Admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("role_name", response.data["errors"])

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
        self.assertFalse(response.data["success"])
        self.assertIn("organization_id", response.data["errors"])

    def test_duplicate_account_returns_structured_validation_error(self):
        User.objects.create_user(
            username="duplicate@example.com",
            email="duplicate@example.com",
            password="ExistingPass123!",
            organization=self.org,
        )

        response = self.client.post(
            "/api/v1/auth/users/",
            {
                "email": "duplicate@example.com",
                "password": "TempPass123!",
                "role_name": "Client User",
                "organization_id": str(self.org.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("email", response.data["errors"])


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

    def test_engineer_role_can_create_core_service_records(self):
        user = User.objects.create_user(
            username="resolver@example.com",
            email="resolver@example.com",
            password="TempPass123!",
        )
        user.roles.add(Role.objects.create(name=Roles.ENGINEER))

        self.assertTrue(user_has_permission(user, "incident:create"))
        self.assertTrue(user_has_permission(user, "problem:create"))
        self.assertTrue(user_has_permission(user, "change:create"))
        self.assertTrue(user_has_permission(user, "service_request:create"))
        self.assertFalse(user_has_permission(user, "incident:assign"))


class RolePermissionAccessTests(APITestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="superadmin@example.com",
            email="superadmin@example.com",
            password="SuperPass123!",
        )
        self.super_admin.roles.add(Role.objects.create(name=Roles.SUPER_ADMIN))

        self.org_admin = User.objects.create_user(
            username="orgadmin@example.com",
            email="orgadmin@example.com",
            password="AdminPass123!",
        )
        self.org_admin.roles.add(Role.objects.create(name=Roles.ORG_ADMIN))
        Permission.objects.create(code="incident:read", description="Read incidents")

    def test_org_admin_cannot_open_role_permission_admin_api(self):
        self.client.force_authenticate(self.org_admin)

        roles_response = self.client.get("/api/v1/auth/roles")
        permissions_response = self.client.get("/api/v1/auth/permissions")

        self.assertEqual(roles_response.status_code, 403)
        self.assertEqual(permissions_response.status_code, 403)

    def test_super_admin_can_open_role_permission_admin_api(self):
        self.client.force_authenticate(self.super_admin)

        roles_response = self.client.get("/api/v1/auth/roles")
        permissions_response = self.client.get("/api/v1/auth/permissions")

        self.assertEqual(roles_response.status_code, 200, roles_response.data)
        self.assertEqual(permissions_response.status_code, 200, permissions_response.data)
