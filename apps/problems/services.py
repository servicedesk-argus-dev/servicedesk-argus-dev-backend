"""
Problem business logic — AI RCA, KB matching, state transitions.

ProblemService encapsulates:
  - run_ai_rca()       → orchestrates AI root-cause analysis
  - match_kb_entries() → finds relevant ALERT_KB entries
  - transition_state() → validates + applies state changes
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from .models import Problem

logger = logging.getLogger(__name__)


class ProblemService:
    """Business logic for Problem operations."""

    @staticmethod
    def run_ai_rca(problem: Problem) -> Problem:
        """
        Trigger AI root-cause analysis for a problem.

        Steps:
          1. Gather linked incidents + alert names
          2. Match ALERT_KB entries
          3. Call AI backend (Ollama / stub)
          4. Store result in problem.root_cause_analysis (JSONField)
          5. Return updated problem

        Returns:
            Updated Problem instance with root_cause_analysis populated.
        """
        from apps.incidents.models import IncidentProblem

        # 1. Gather evidence from linked incidents
        linked = IncidentProblem.objects.filter(problem=problem).select_related(
            "incident"
        )
        incidents_data = []
        alert_names = []

        for link in linked:
            inc = link.incident
            incidents_data.append(
                {
                    "number": inc.number,
                    "description": inc.short_description,
                    "state": inc.state,
                    "priority": inc.priority,
                    "alert_name": inc.source_alert_name or "",
                }
            )
            if inc.source_alert_name:
                alert_names.append(inc.source_alert_name)

        # 2. Match KB entries
        kb_entries = ProblemService.match_kb_entries(alert_names)

        # 3. Call AI backend
        ai_result = ProblemService._call_ai_backend(
            problem=problem,
            incidents=incidents_data,
            kb_entries=kb_entries,
        )

        # 4. Persist result
        with transaction.atomic():
            problem.root_cause_analysis = ai_result
            problem.save(update_fields=["root_cause_analysis", "updated_at"])

        logger.info(
            "AI RCA completed for problem %s (confidence: %s%%)",
            problem.number,
            ai_result.get("confidence", 0),
        )
        return problem

    @staticmethod
    def match_kb_entries(alert_names: list[str]) -> list[dict]:
        """
        Match alert names against ALERT_KB.

        For now, returns a static KB. In production, this would query
        a real KB table or external service.

        Args:
            alert_names: List of alert names from linked incidents.

        Returns:
            List of KB entries (dicts with key, category, rootCauses, etc.)
        """
        # Static ALERT_KB for demo — replace with DB query in production
        ALERT_KB = [
            {
                "key": "HighCPU",
                "category": "Performance",
                "rootCauses": [
                    "Runaway process consuming CPU cycles",
                    "Insufficient CPU allocation for workload",
                    "CPU throttling due to thermal limits",
                ],
                "investigate": [
                    "top -bn1 | head -20",
                    "ps aux --sort=-%cpu | head -10",
                    "cat /proc/cpuinfo | grep MHz",
                ],
                "remediate": [
                    "kill -9 <PID> for runaway process",
                    "Increase CPU limits in container/VM config",
                    "Check cooling system and thermal paste",
                ],
                "blastRadius": "Single host or pod",
            },
            {
                "key": "HighMemory",
                "category": "Performance",
                "rootCauses": [
                    "Memory leak in application",
                    "Insufficient memory allocation",
                    "Large dataset loaded into memory",
                ],
                "investigate": [
                    "free -h",
                    "ps aux --sort=-%mem | head -10",
                    "cat /proc/meminfo",
                ],
                "remediate": [
                    "Restart leaking service",
                    "Increase memory limits",
                    "Optimize data loading strategy",
                ],
                "blastRadius": "Single host or pod",
            },
            {
                "key": "DiskFull",
                "category": "Storage",
                "rootCauses": [
                    "Log files filling disk",
                    "Temporary files not cleaned up",
                    "Database growth exceeding capacity",
                ],
                "investigate": [
                    "df -h",
                    "du -sh /* | sort -rh | head -10",
                    "find /var/log -type f -size +100M",
                ],
                "remediate": [
                    "Rotate and compress logs",
                    "Clean /tmp and /var/tmp",
                    "Expand disk or archive old data",
                ],
                "blastRadius": "Single host",
            },
            {
                "key": "ServiceDown",
                "category": "Availability",
                "rootCauses": [
                    "Process crashed or killed",
                    "Configuration error preventing startup",
                    "Dependency service unavailable",
                ],
                "investigate": [
                    "systemctl status <service>",
                    "journalctl -u <service> -n 50",
                    "netstat -tuln | grep <port>",
                ],
                "remediate": [
                    "systemctl restart <service>",
                    "Fix config and reload",
                    "Restore dependency service",
                ],
                "blastRadius": "Service-level",
            },
            {
                "key": "NetworkLatency",
                "category": "Network",
                "rootCauses": [
                    "Network congestion",
                    "Routing issues",
                    "Packet loss",
                ],
                "investigate": [
                    "ping -c 10 <target>",
                    "traceroute <target>",
                    "mtr --report <target>",
                ],
                "remediate": [
                    "Check switch/router health",
                    "Adjust QoS policies",
                    "Reroute traffic via alternate path",
                ],
                "blastRadius": "Network segment",
            },
        ]

        # Simple substring match
        matched = []
        for kb in ALERT_KB:
            for alert_name in alert_names:
                if kb["key"].lower() in alert_name.lower():
                    matched.append(kb)
                    break
        return matched

    @staticmethod
    def _call_ai_backend(
        problem: Problem,
        incidents: list[dict],
        kb_entries: list[dict],
    ) -> dict:
        """
        Call AI backend (Ollama / OpenAI / stub) for RCA.

        In production, this would:
          - Format a prompt with problem context + incidents + KB
          - Call Ollama API (or OpenAI, Anthropic, etc.)
          - Parse the response into structured JSON

        For now, returns a mock response.

        Args:
            problem: Problem instance
            incidents: List of linked incident dicts
            kb_entries: Matched KB entries

        Returns:
            Dict with rootCause, confidence, evidence, workaround, permanentFix, category
        """
        # Mock AI response — replace with real API call
        incident_count = len(incidents)
        kb_count = len(kb_entries)

        # Extract category from KB if available
        category = kb_entries[0]["category"] if kb_entries else problem.category or "Unknown"

        # Build evidence list
        evidence = [
            f"{incident_count} linked incident(s) analyzed",
            f"{kb_count} knowledge base match(es) found",
        ]
        if incidents:
            evidence.append(
                f"Most recent incident: {incidents[0]['number']} ({incidents[0]['priority']})"
            )

        # Build root cause from KB or generic
        if kb_entries:
            root_causes = kb_entries[0]["rootCauses"]
            root_cause = root_causes[0] if root_causes else "Root cause under investigation"
            workaround = kb_entries[0]["remediate"][0] if kb_entries[0].get("remediate") else None
        else:
            root_cause = (
                f"Multiple incidents ({incident_count}) suggest a recurring issue. "
                "Further investigation required to identify root cause."
            )
            workaround = None

        # Confidence based on KB match + incident count
        confidence = 50
        if kb_entries:
            confidence += 30
        if incident_count >= 3:
            confidence += 20
        confidence = min(confidence, 95)

        return {
            "rootCause": root_cause,
            "confidence": confidence,
            "evidence": evidence,
            "workaround": workaround,
            "permanentFix": "Implement monitoring and auto-remediation for this pattern",
            "category": category,
            "aiModel": "mock-ai-v1",
            "timestamp": problem.updated_at.isoformat(),
        }

    @staticmethod
    def transition_state(problem: Problem, new_state: str) -> Problem:
        """
        Validate and apply state transition.

        Args:
            problem: Problem instance
            new_state: Target state

        Returns:
            Updated Problem instance

        Raises:
            ValueError: If transition is not allowed
        """
        from .models import Problem as ProblemModel

        transitions = {
            ProblemModel.State.NEW: [ProblemModel.State.INVESTIGATION],
            ProblemModel.State.INVESTIGATION: [
                ProblemModel.State.RCA_IN_PROGRESS,
                ProblemModel.State.KNOWN_ERROR,
            ],
            ProblemModel.State.RCA_IN_PROGRESS: [
                ProblemModel.State.KNOWN_ERROR,
                ProblemModel.State.RESOLVED,
            ],
            ProblemModel.State.KNOWN_ERROR: [ProblemModel.State.RESOLVED],
            ProblemModel.State.RESOLVED: [ProblemModel.State.CLOSED],
            ProblemModel.State.CLOSED: [],
        }

        allowed = transitions.get(problem.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Cannot transition from '{problem.state}' to '{new_state}'. "
                f"Allowed: {allowed or ['none']}."
            )

        problem.state = new_state
        if new_state == ProblemModel.State.KNOWN_ERROR:
            problem.is_known_error = True
        problem.save(update_fields=["state", "is_known_error", "updated_at"])

        logger.info(
            "Problem %s transitioned to %s",
            problem.number,
            new_state,
        )
        return problem
