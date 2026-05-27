from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization
from apps.changes.models import Change
from .models import ApprovalRequest, Approver
from .services import create_approval_request, process_approval_action

User = get_user_model()

class ApprovalTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="password123",
            organization=self.org
        )
        self.approver_user = User.objects.create_user(
            username="approver", email="app@example.com", password="password123",
            organization=self.org
        )
        self.change = Change.objects.create(
            short_description="Test Change",
            organization=self.org,
            created_by=self.admin,
            type="Normal"
        )

    def test_create_approval_request(self):
        request = create_approval_request(
            self.change, 
            "Approve Change", 
            [self.approver_user],
            "Needs CAB approval"
        )
        self.assertEqual(request.title, "Approve Change")
        self.assertEqual(request.approvers.count(), 1)
        self.assertEqual(request.state, ApprovalRequest.State.PENDING)

    def test_approve_flow(self):
        req = create_approval_request(self.change, "Test", [self.approver_user])
        approver = req.approvers.first()
        
        process_approval_action(approver.id, 'APPROVE', "Looks good")
        
        req.refresh_from_db()
        self.assertEqual(req.state, ApprovalRequest.State.APPROVED)

    def test_reject_flow(self):
        req = create_approval_request(self.change, "Test", [self.approver_user])
        approver = req.approvers.first()
        
        process_approval_action(approver.id, 'REJECT', "No way")
        
        req.refresh_from_db()
        self.assertEqual(req.state, ApprovalRequest.State.REJECTED)
