from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.organizations.models import Organization


User = get_user_model()


class WorkflowE2ETests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Workflow Org", slug="workflow-org")
        self.user = User.objects.create_user(
            username="workflow.user",
            email="workflow@example.com",
            password="Password@123",
            organization=self.org,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

    def _create_incident(self):
        payload = {
            "short_description": "Database CPU alert",
            "description": "prod db cpu > 95%",
            "impact": "ENTERPRISE",
            "urgency": "CRITICAL",
            "category": "Database",
            "source": "PROMETHEUS",
        }
        response = self.client.post("/api/v1/incidents/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["data"]["id"]

    def _create_problem(self):
        payload = {
            "short_description": "Recurring db contention",
            "description": "Intermittent lock wait spikes",
            "priority": "P2",
            "category": "Database",
        }
        response = self.client.post("/api/v1/problems/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["data"]["id"]

    def _create_change(self):
        payload = {
            "short_description": "Tune postgres parameters",
            "description": "Adjust work_mem and autovacuum",
            "type": "NORMAL",
            "risk_level": "MEDIUM",
            "category": "Database",
        }
        response = self.client.post("/api/v1/changes/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["data"]["id"]

    def test_incident_end_to_end_lifecycle(self):
        incident_id = self._create_incident()

        # NEW -> ON_HOLD requires hold reason
        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "ON_HOLD"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "ON_HOLD", "hold_reason": "AWAITING_VENDOR"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["state"], "ON_HOLD")

        # ON_HOLD -> IN_PROGRESS
        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "IN_PROGRESS"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        # IN_PROGRESS -> RESOLVED requires resolution metadata
        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "RESOLVED"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {
                "state": "RESOLVED",
                "resolution_code": "WORKAROUND_APPLIED",
                "resolution_notes": "Routed traffic to replica.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["state"], "RESOLVED")

        # RESOLVED -> CLOSED
        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "CLOSED"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["state"], "CLOSED")

        # CLOSED -> IN_PROGRESS (reopen)
        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "IN_PROGRESS"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["state"], "IN_PROGRESS")

    def test_incident_list_serializes_hierarchy_fields(self):
        parent_id = self._create_incident()
        response = self.client.post(
            "/api/v1/incidents/",
            {
                "short_description": "Child database alert",
                "description": "Replica cpu > 95%",
                "impact": "TEAM",
                "urgency": "MEDIUM",
                "category": "Database",
                "source": "PROMETHEUS",
                "parent": parent_id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        child_id = response.data["data"]["id"]

        response = self.client.get("/api/v1/incidents/?page=1&limit=25")
        self.assertEqual(response.status_code, 200, response.data)

        incidents = {item["id"]: item for item in response.data["data"]}
        self.assertIn(parent_id, incidents)
        self.assertIn(child_id, incidents)
        self.assertEqual(incidents[parent_id]["hierarchy_level"], 0)
        self.assertEqual(incidents[parent_id]["child_status_summary"]["total"], 1)
        self.assertEqual(incidents[child_id]["hierarchy_level"], 1)
        self.assertEqual(incidents[child_id]["parent"]["id"], parent_id)
        self.assertEqual(incidents[child_id]["root_parent"]["id"], parent_id)

    def test_problem_end_to_end_lifecycle_with_reopen(self):
        problem_id = self._create_problem()

        transitions = [
            "INVESTIGATION",
            "RCA_IN_PROGRESS",
            "KNOWN_ERROR",
            "RESOLVED",
            "CLOSED",
            "INVESTIGATION",  # reopen
        ]
        for state in transitions:
            response = self.client.patch(
                f"/api/v1/problems/{problem_id}/",
                {"state": state},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["data"]["state"], state)

    def test_change_end_to_end_lifecycle_with_required_gates(self):
        change_id = self._create_change()

        # NEW -> ASSESSMENT
        response = self.client.patch(
            f"/api/v1/changes/{change_id}/",
            {"state": "ASSESSMENT"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        # ASSESSMENT -> APPROVAL requires plans
        response = self.client.patch(
            f"/api/v1/changes/{change_id}/",
            {"state": "APPROVAL"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

        response = self.client.patch(
            f"/api/v1/changes/{change_id}/",
            {
                "state": "APPROVAL",
                "implementation_plan": "Apply config via rolling restart",
                "rollback_plan": "Restore previous parameters",
                "test_plan": "Verify CPU and latency for 30 mins",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        # APPROVAL -> SCHEDULED -> IMPLEMENTING -> REVIEW
        for state in ["SCHEDULED", "IMPLEMENTING", "REVIEW"]:
            response = self.client.patch(
                f"/api/v1/changes/{change_id}/",
                {"state": state},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["data"]["state"], state)

        # REVIEW -> CLOSED requires review notes + closure code
        response = self.client.patch(
            f"/api/v1/changes/{change_id}/",
            {"state": "CLOSED"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

        response = self.client.patch(
            f"/api/v1/changes/{change_id}/",
            {
                "state": "CLOSED",
                "review_notes": "Post implementation checks successful",
                "closure_code": "SUCCESSFUL",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["state"], "CLOSED")

    def test_incident_rejects_invalid_controlled_values(self):
        incident_id = self._create_incident()

        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {"state": "ON_HOLD", "hold_reason": "SOME_RANDOM_REASON"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("hold_reason", response.data)

        response = self.client.patch(
            f"/api/v1/incidents/{incident_id}/",
            {
                "state": "RESOLVED",
                "resolution_code": "INVALID_CODE",
                "resolution_notes": "Investigated and fixed.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("resolution_code", response.data)

