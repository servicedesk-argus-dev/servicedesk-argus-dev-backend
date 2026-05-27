from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from apps.common.permissions import Roles
from apps.notifications.models import Notification
from apps.notifications.realtime import _user_from_token
from apps.notifications.services import broadcast_notification
from apps.organizations.models import Organization

User = get_user_model()


class NotificationRealtimeServiceTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Client A", slug="client-a")
        self.org_b = Organization.objects.create(name="Client B", slug="client-b")
        self.engineer_role = Role.objects.create(name=Roles.ENGINEER)
        self.client_role = Role.objects.create(name=Roles.CLIENT_USER)

        self.staff = User.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="Password@123",
        )
        self.staff.roles.add(self.engineer_role)
        self.client_a = User.objects.create_user(
            username="client.a@example.com",
            email="client.a@example.com",
            password="Password@123",
            organization=self.org_a,
        )
        self.client_a.roles.add(self.client_role)
        self.client_b = User.objects.create_user(
            username="client.b@example.com",
            email="client.b@example.com",
            password="Password@123",
            organization=self.org_b,
        )
        self.client_b.roles.add(self.client_role)

    @patch("apps.notifications.services.emit_notification")
    def test_explicit_user_notification_emits_only_to_that_user(self, emit_notification):
        broadcast_notification(
            self.org_a,
            "Incident assigned to you",
            resource_type="INCIDENT",
            resource_id="abc123",
            user=self.client_a,
        )

        self.assertEqual(Notification.objects.count(), 1)
        notification = Notification.objects.get()
        self.assertEqual(notification.user, self.client_a)
        self.assertEqual(notification.organization, self.org_a)
        self.assertEqual(notification.link, "/incidents/abc123")
        emit_notification.assert_called_once_with(notification)

    @patch("apps.notifications.services.emit_notification")
    def test_org_broadcast_never_notifies_another_client_org(self, emit_notification):
        broadcast_notification(
            self.org_a,
            "New Incident Created: Test",
            resource_type="INCIDENT",
            resource_id="inc123",
        )

        recipients = set(Notification.objects.values_list("user__email", flat=True))
        self.assertIn(self.staff.email, recipients)
        self.assertIn(self.client_a.email, recipients)
        self.assertNotIn(self.client_b.email, recipients)
        self.assertEqual(emit_notification.call_count, Notification.objects.count())

    def test_socket_token_resolves_active_user(self):
        token = RefreshToken.for_user(self.client_a).access_token
        self.assertEqual(_user_from_token(str(token)), self.client_a)


class NotificationRealtimeApiTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="API Client A", slug="api-client-a")
        self.org_b = Organization.objects.create(name="API Client B", slug="api-client-b")
        self.admin_role = Role.objects.create(name=Roles.SUPER_ADMIN)
        self.admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="Password@123",
        )
        self.admin.roles.add(self.admin_role)
        self.n1 = Notification.objects.create(
            user=self.admin,
            organization=self.org_a,
            type=Notification.Type.SYSTEM,
            title="A",
            message="First notification",
        )
        self.n2 = Notification.objects.create(
            user=self.admin,
            organization=self.org_b,
            type=Notification.Type.SYSTEM,
            title="B",
            message="Second notification",
        )
        token = RefreshToken.for_user(self.admin).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_internal_unread_count_without_selected_org_counts_all_user_notifications(self):
        response = self.client.get("/api/v1/notifications/unread-count")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["count"], 2)

    @patch("apps.notifications.views.emit_notification_read")
    def test_mark_single_read_updates_database_and_emits_event(self, emit_read):
        response = self.client.patch(f"/api/v1/notifications/{self.n1.id}/read")

        self.assertEqual(response.status_code, 200, response.data)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)
        emit_read.assert_called_once()
        self.assertEqual(emit_read.call_args.args[0], self.admin.id)
        self.assertEqual(emit_read.call_args.args[1], self.n1.id)
        self.assertEqual(emit_read.call_args.kwargs["unread_count"], 1)

    @patch("apps.notifications.views.emit_notifications_read_all")
    def test_mark_all_read_updates_database_and_emits_event(self, emit_read_all):
        response = self.client.post("/api/v1/notifications/read-all")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Notification.objects.filter(user=self.admin, is_read=False).exists())
        emit_read_all.assert_called_once_with(self.admin.id)
