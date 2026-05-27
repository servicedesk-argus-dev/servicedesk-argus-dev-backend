import uuid
from django.db import models

class IntegrationType(models.TextChoices):
    PROMETHEUS = "PROMETHEUS", "Prometheus"
    GRAFANA = "GRAFANA", "Grafana"
    LOKI = "LOKI", "Loki"
    KUBERNETES_CLUSTER = "KUBERNETES_CLUSTER", "Kubernetes Cluster"
    STACKSTORM = "STACKSTORM", "StackStorm"
    DATADOG = "DATADOG", "Datadog"
    NEW_RELIC = "NEW_RELIC", "New Relic"
    ELASTICSEARCH = "ELASTICSEARCH", "Elasticsearch"
    PAGERDUTY = "PAGERDUTY", "PagerDuty"
    SERVICENOW = "SERVICENOW", "ServiceNow"
    JIRA = "JIRA", "Jira"
    OPSGENIE = "OPSGENIE", "OpsGenie"
    REDMINE = "REDMINE", "Redmine"
    SLACK = "SLACK", "Slack"
    TEAMS = "TEAMS", "Microsoft Teams"
    APPRISE = "APPRISE", "Apprise"
    TWILIO = "TWILIO", "Twilio"
    MSG91 = "MSG91", "MSG91"
    WEBHOOK = "WEBHOOK", "Generic Webhook"
    EMAIL = "EMAIL", "Email Inbound"
    N8N = "N8N", "n8n"
    ANSIBLE = "ANSIBLE", "Ansible"
    TERRAFORM = "TERRAFORM", "Terraform"
    VAULT = "VAULT", "HashiCorp Vault"
    AWS = "AWS", "AWS CloudWatch"
    AZURE = "AZURE", "Azure Monitor"

class Integration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", 
        on_delete=models.CASCADE, 
        related_name="integrations"
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=IntegrationType.choices)
    config = models.JSONField(default=dict) # e.g., {"webhook_url": "...", "channel": "#alerts"}
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations"
        ordering = ["-created_at"]
