from config.celery import app
from .models import Integration, IntegrationType
from .dispatcher import dispatch_to_slack, dispatch_to_teams, dispatch_to_webhook

@app.task(name="apps.integrations.tasks.notify_integrations")
def notify_integrations_task(organization_id, message, resource_type=None, resource_id=None):
    integrations = Integration.objects.filter(organization_id=organization_id, is_active=True)
    
    for integration in integrations:
        config = integration.config
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            continue
            
        if integration.type == IntegrationType.SLACK:
            dispatch_to_slack(webhook_url, message)
        elif integration.type == IntegrationType.TEAMS:
            dispatch_to_teams(webhook_url, message)
        elif integration.type == IntegrationType.WEBHOOK:
            dispatch_to_webhook(webhook_url, {
                "message": message, 
                "resource_type": resource_type, 
                "resource_id": str(resource_id) if resource_id else None
            })
