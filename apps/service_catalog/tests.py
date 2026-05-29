from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.organizations.models import Organization

from .models import CatalogCategory, CatalogItem, ServiceRequest

User = get_user_model()


class ServiceRequestCreateTests(TestCase):
    def test_internal_user_without_org_header_uses_selected_catalog_item_org(self):
        default_org = Organization.objects.create(name="Default Client", slug="default-client")
        catalog_org = Organization.objects.create(name="Catalog Client", slug="catalog-client")
        category = CatalogCategory.objects.create(
            organization=catalog_org,
            name="Access",
            description="Access services",
        )
        item = CatalogItem.objects.create(
            organization=catalog_org,
            category=category,
            name="VPN Access",
            short_description="VPN access",
            description="Request VPN access",
        )
        admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminPass123!",
            organization=default_org,
        )
        admin.roles.add(Role.objects.create(name="Super Admin"))

        client = APIClient()
        client.force_authenticate(admin)
        response = client.post(
            "/api/v1/service-requests/",
            {
                "catalogItemId": str(item.id),
                "shortDescription": "Need VPN access",
                "priority": "P3",
                "quantity": 1,
                "variables": {"business_justification": "Onboarding"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        service_request = ServiceRequest.objects.get(id=response.data["data"]["id"])
        self.assertEqual(service_request.organization, catalog_org)

