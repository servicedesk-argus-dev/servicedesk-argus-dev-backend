from celery import shared_task

from .models import ConfigurationItem
from .services import AssetLiveStatusService, PrometheusConfigService


@shared_task
def refresh_asset_live_status(asset_id):
    asset = ConfigurationItem.objects.get(id=asset_id)
    return AssetLiveStatusService.refresh(asset)


@shared_task
def refresh_org_asset_live_status(organization_id):
    refreshed = 0
    for asset in ConfigurationItem.objects.filter(organization_id=organization_id, monitoring_enabled=True):
        AssetLiveStatusService.refresh(asset)
        refreshed += 1
    return {"refreshed": refreshed}


@shared_task
def generate_org_prometheus_config(organization_id):
    path, _content = PrometheusConfigService.write(organization_id)
    return {"path": str(path)}
