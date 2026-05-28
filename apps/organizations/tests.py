from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.common.permissions import Roles
from apps.organizations.models import Organization


User = get_user_model()


class OrganizationManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminPass123!",
        )
        self.admin.roles.add(Role.objects.create(name=Roles.SUPER_ADMIN))
        self.manager = User.objects.create_user(
            username="manager@example.com",
            email="manager@example.com",
            password="ManagerPass123!",
        )
        self.manager.roles.add(Role.objects.create(name=Roles.MANAGER))

    def test_admin_can_create_client_with_name_only(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/v1/organizations/",
            {"name": "Finspot Capital"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["name"], "Finspot Capital")
        self.assertEqual(response.data["slug"], "finspot-capital")
        self.assertTrue(Organization.objects.filter(slug="finspot-capital").exists())

    def test_manager_cannot_create_client(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            "/api/v1/organizations/",
            {"name": "Blocked Client"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])

    def test_duplicate_client_name_returns_structured_error(self):
        Organization.objects.create(name="Existing Client", slug="existing-client")
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/v1/organizations/",
            {"name": "Existing Client"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("name", response.data["errors"])
