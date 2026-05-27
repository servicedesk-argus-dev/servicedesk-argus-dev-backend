from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.organizations.models import Organization

UserModel = get_user_model()


class ITSMRBACTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="RBAC Org", slug="rbac-org")
        self.operator = UserModel.objects.create_user(
            username="op.user",
            email="op@example.com",
            password="Password@123",
            organization=self.org,
            role=User.Role.OPERATOR,
        )
        self.engineer = UserModel.objects.create_user(
            username="eng.user",
            email="eng@example.com",
            password="Password@123",
            organization=self.org,
            role=User.Role.ENGINEER,
        )
        refresh = RefreshToken.for_user(self.operator)
        self.operator_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {str(refresh.access_token)}",
            "HTTP_X_ORGANIZATION_ID": str(self.org.id),
        }
        refresh_e = RefreshToken.for_user(self.engineer)
        self.engineer_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {str(refresh_e.access_token)}",
            "HTTP_X_ORGANIZATION_ID": str(self.org.id),
        }

    def _create_incident(self, headers):
        payload = {
            "short_description": "RBAC test",
            "description": "desc",
            "impact": "TEAM",
            "urgency": "MEDIUM",
            "category": "Other",
            "source": "MANUAL",
        }
        self.client.credentials(**headers)
        response = self.client.post("/api/v1/incidents/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["data"]["id"]

    def test_operator_cannot_resolve_incident(self):
        iid = self._create_incident(self.operator_headers)
        self.client.credentials(**self.operator_headers)
        response = self.client.patch(
            f"/api/v1/incidents/{iid}/",
            {
                "state": "RESOLVED",
                "resolution_code": "PERMANENT_FIX",
                "resolution_notes": "fixed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)

    def test_engineer_can_resolve_incident(self):
        iid = self._create_incident(self.engineer_headers)
        self.client.credentials(**self.engineer_headers)
        response = self.client.patch(
            f"/api/v1/incidents/{iid}/",
            {
                "state": "RESOLVED",
                "resolution_code": "PERMANENT_FIX",
                "resolution_notes": "fixed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
