from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from apps.organizations.models import Organization
from apps.incidents.models import Incident
from .models import Workflow, WorkflowState, WorkflowTransition

class WorkflowTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.workflow = Workflow.objects.create(
            name="Incident Workflow",
            organization=self.org,
            target_content_type=ContentType.objects.get_for_model(Incident)
        )
        self.state_new = WorkflowState.objects.create(
            workflow=self.workflow,
            name="New",
            is_initial=True
        )
        self.state_resolved = WorkflowState.objects.create(
            workflow=self.workflow,
            name="Resolved"
        )

    def test_workflow_structure(self):
        self.assertEqual(self.workflow.states.count(), 2)
        self.assertEqual(self.workflow.initial_state, self.state_new)

    def test_create_transition(self):
        transition = WorkflowTransition.objects.create(
            workflow=self.workflow,
            from_state=self.state_new,
            to_state=self.state_resolved,
            name="Resolve"
        )
        self.assertEqual(transition.name, "Resolve")
        self.assertEqual(self.state_new.outgoing_transitions.count(), 1)
