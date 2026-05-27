from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.assets.models import ConfigurationItem
from apps.organizations.models import Organization


def get_jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class OrgIsolationTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name='Org A', slug='org-a', is_active=True)
        cls.org_b = Organization.objects.create(name='Org B', slug='org-b', is_active=True)

        cls.user_a = User.objects.create_user(
            username='user_a',
            password='testpass123',
            organization=cls.org_a,
        )
        cls.user_b = User.objects.create_user(
            username='user_b',
            password='testpass123',
            organization=cls.org_b,
        )

        cls.ci_a = ConfigurationItem.objects.create(
            name='Server A',
            organization=cls.org_a,
            type='SERVER',
            status='LIVE',
        )
        cls.ci_b = ConfigurationItem.objects.create(
            name='Server B',
            organization=cls.org_b,
            type='SERVER',
            status='LIVE',
        )

    def setUp(self):
        self.client_a = APIClient()
        self.client_a.credentials(
            HTTP_AUTHORIZATION='Bearer ' + get_jwt_for_user(self.user_a),
            HTTP_X_ORGANIZATION_ID=str(self.org_a.id),
        )
        self.client_b = APIClient()
        self.client_b.credentials(
            HTTP_AUTHORIZATION='Bearer ' + get_jwt_for_user(self.user_b),
            HTTP_X_ORGANIZATION_ID=str(self.org_b.id),
        )

    def test_user_a_can_list_own_assets(self):
        response = self.client_a.get('/api/v1/assets/')
        self.assertEqual(response.status_code, 200)
        items = response.data.get('data', response.data)
        ids = [item['id'] for item in items]
        self.assertIn(str(self.ci_a.id), ids)
        self.assertNotIn(str(self.ci_b.id), ids)

    def test_user_a_cannot_retrieve_org_b_asset(self):
        response = self.client_a.get(f'/api/v1/assets/{self.ci_b.id}/')
        self.assertIn(response.status_code, [403, 404])

    def test_user_a_cannot_update_org_b_asset(self):
        response = self.client_a.patch(
            f'/api/v1/assets/{self.ci_b.id}/',
            {'name': 'hacked'},
            format='json',
        )
        self.assertIn(response.status_code, [403, 404])

    def test_org_b_header_rejected_for_user_a(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + get_jwt_for_user(self.user_a),
            HTTP_X_ORGANIZATION_ID=str(self.org_b.id),
        )
        response = client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, 403)

    def test_invalid_uuid_org_header_returns_400(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + get_jwt_for_user(self.user_a),
            HTTP_X_ORGANIZATION_ID='not-a-uuid',
        )
        response = client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, 400)
