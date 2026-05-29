import json

from django.http import HttpResponse
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.common.audit import MASKED_VALUE, create_audit_log
from apps.organizations.models import Organization
from apps.common.rate_limit_middleware import RateLimitMiddleware
from apps.common.audit_middleware import AuditLogMiddleware
from apps.common.models import AuditLog

User = get_user_model()

class MiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123",
            organization=self.org
        )
        cache.clear()

    def test_rate_limiting_user(self):
        middleware = RateLimitMiddleware(lambda r: None)
        request = self.factory.get('/api/test')
        request.user = self.user
        request.organization = self.org

        # Trigger 101 requests (limit is 100)
        for i in range(100):
            response = middleware(request)
            self.assertIsNone(response) # None means it passed through

        # 101st request
        response = middleware(request)
        self.assertEqual(response.status_code, 429)

    def test_audit_logging_middleware_masks_sensitive_payload_and_records_metadata(self):
        middleware = AuditLogMiddleware(lambda r: HttpResponse("created", status=201))
        
        request = self.factory.post(
            '/api/v1/incidents/',
            data=json.dumps({
                "short_description": "New",
                "password": "plain-secret",
                "nested": {"accessToken": "token-value"},
            }),
            content_type="application/json",
            HTTP_X_CORRELATION_ID="trace-123",
        )
        request.user = self.user
        request.organization = self.org
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        response = middleware(request)
        self.assertEqual(response.status_code, 201)
        
        log = AuditLog.objects.get(user=self.user, action="POST_INCIDENTS")
        self.assertEqual(log.organization, self.org)
        self.assertEqual(log.actor_email, self.user.email)
        self.assertEqual(log.method, "POST")
        self.assertEqual(log.path, "/api/v1/incidents/")
        self.assertEqual(log.status_code, 201)
        self.assertEqual(log.correlation_id, "trace-123")
        self.assertEqual(log.request_payload["short_description"], "New")
        self.assertEqual(log.request_payload["password"], MASKED_VALUE)
        self.assertEqual(log.request_payload["nested"]["accessToken"], MASKED_VALUE)
        self.assertEqual(log.response_payload, {"status_code": 201})

    def test_audit_logging_middleware_records_server_errors_safely(self):
        middleware = AuditLogMiddleware(lambda r: HttpResponse("failed", status=500))
        request = self.factory.patch(
            '/api/v1/incidents/11111111-1111-1111-1111-111111111111/',
            data=json.dumps({"refresh_token": "should-not-persist"}),
            content_type="application/json",
        )
        request.user = self.user
        request.organization = self.org
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        response = middleware(request)
        self.assertEqual(response.status_code, 500)

        log = AuditLog.objects.get(action="PATCH_INCIDENTS_FAILED")
        self.assertEqual(log.resource_id, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(log.status_code, 500)
        self.assertEqual(log.request_payload["refresh_token"], MASKED_VALUE)

    def test_manual_audit_log_masks_payload(self):
        request = self.factory.post('/api/v1/auth/keycloak-login')
        request.user = self.user
        request.organization = self.org
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        log = create_audit_log(
            request,
            "KEYCLOAK_LOGIN_FAILED",
            "USER",
            payload={"accessToken": "secret-token", "email": "person@example.com"},
            status_code=401,
        )

        self.assertEqual(log.request_payload["accessToken"], MASKED_VALUE)
        self.assertEqual(log.request_payload["email"], "person@example.com")
        self.assertEqual(log.status_code, 401)

    def test_audit_resource_types_include_all_orgs_for_super_admin(self):
        other_org = Organization.objects.create(name="Other Org", slug="other-org")
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        AuditLog.objects.create(organization=self.org, action="INCIDENT_CREATED", resource_type="INCIDENT", description="")
        AuditLog.objects.create(organization=other_org, action="CHANGE_CREATED", resource_type="CHANGE", description="")

        client = APIClient()
        client.force_authenticate(admin)
        response = client.get("/api/v1/audit/resource-types/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["data"]), {"INCIDENT", "CHANGE"})

    def test_audit_detail_endpoint_is_append_only(self):
        admin = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="password123",
        )
        log = AuditLog.objects.create(organization=self.org, action="INCIDENT_CREATED", resource_type="INCIDENT", description="")

        client = APIClient()
        client.force_authenticate(admin)
        response = client.patch(f"/api/v1/audit/logs/{log.id}/", {"description": "tamper"}, format="json")

        self.assertEqual(response.status_code, 405)
        log.refresh_from_db()
        self.assertEqual(log.description, "")
