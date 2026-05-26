from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.conf import settings

from apps.organizations.models import Organization
from apps.teams.models import Team, TeamMember

from .models import (
    AssetCatalog,
    AssetManagementEndpoint,
    AssetPortConnection,
    AssetRelationship,
    AssetSite,
    ConfigurationItem,
)


User = get_user_model()


@dataclass(frozen=True)
class SeedAsset:
    external_id: str
    name: str
    type: str
    status: str
    category: str
    subcategory: str
    hostname: str | None
    ip_address: str | None
    management_ip_address: str | None
    site_slug: str
    team_name: str
    owner_email: str | None
    service_name: str | None
    manufacturer: str | None = None
    model: str | None = None
    os: str | None = None
    os_version: str | None = None
    rack_position: str | None = None
    prometheus_job: str | None = None
    monitoring_enabled: bool = True
    location: str | None = None
    cpu: str | None = None
    memory: str | None = None
    storage: str | None = None
    metadata: dict | None = None


SEED_SITES = [
    {
        "slug": "production",
        "name": "Production DC",
        "environment": "Production",
        "location": "Primary Datacenter",
        "country": "India",
        "state": "Tamil Nadu",
        "status": AssetSite.Status.ACTIVE,
    },
    {
        "slug": "dr-site",
        "name": "DR Site",
        "environment": "Disaster Recovery",
        "location": "Secondary Datacenter",
        "country": "India",
        "state": "Karnataka",
        "status": AssetSite.Status.ACTIVE,
    },
]


SEED_CATALOG = {
    AssetCatalog.Category.SERVER_TYPE: ["Application Server", "Database Server", "Virtualization Host"],
    AssetCatalog.Category.SERVER_OS: ["Ubuntu 22.04", "RHEL 9", "Windows Server 2022"],
    AssetCatalog.Category.SERVER_SOFTWARE: ["Docker Engine", "Nginx", "Prometheus Node Exporter", "PostgreSQL"],
    AssetCatalog.Category.SERVER_NIC: ["1GbE Copper", "10GbE SFP+", "25GbE"],
    AssetCatalog.Category.SWITCH_LAYER: ["Layer 2", "Layer 3"],
    AssetCatalog.Category.SWITCH_MODEL: ["Cisco Nexus 93180YC-FX", "Aruba 8325"],
    AssetCatalog.Category.FIREWALL_TYPE: ["Perimeter Firewall", "Internal Segmentation Firewall"],
    AssetCatalog.Category.FIREWALL_MODEL: ["Palo Alto PA-3220", "FortiGate 200F"],
    AssetCatalog.Category.ROUTER_TYPE: ["Edge Router", "WAN Router"],
    AssetCatalog.Category.ROUTER_MODEL: ["Cisco ASR 1001-X", "Juniper MX204"],
    AssetCatalog.Category.SOFTWARE: ["Grafana", "Prometheus", "Loki", "Keycloak"],
    AssetCatalog.Category.APPLICATION: ["Argus Service Desk", "Customer Portal", "Monitoring API"],
}


SEED_ASSETS: tuple[SeedAsset, ...] = (
    SeedAsset(
        external_id="seed:argus-web-01",
        name="argus-web-01",
        type=ConfigurationItem.Type.APPLICATION,
        status=ConfigurationItem.Status.LIVE,
        category="Application",
        subcategory="React Frontend",
        hostname="argus-web-01",
        ip_address="10.10.20.10",
        management_ip_address="10.10.20.10",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Argus Service Desk UI",
        manufacturer="OpenJS",
        model="Vite",
        metadata={"tier": "web", "linkedeye_family": "application"},
    ),
    SeedAsset(
        external_id="seed:argus-api-01",
        name="argus-api-01",
        type=ConfigurationItem.Type.SERVER,
        status=ConfigurationItem.Status.LIVE,
        category="Infrastructure",
        subcategory="Application Server",
        hostname="argus-api-01",
        ip_address="10.10.10.12",
        management_ip_address="10.10.10.12",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Argus API",
        manufacturer="Dell",
        model="PowerEdge R650",
        os="Ubuntu",
        os_version="22.04 LTS",
        rack_position="R1-U10",
        prometheus_job="server",
        cpu="16 vCPU",
        memory="64 GB",
        storage="1.5 TB SSD",
        metadata={"tier": "app", "linkedeye_family": "server"},
    ),
    SeedAsset(
        external_id="seed:argus-api-02",
        name="argus-api-02",
        type=ConfigurationItem.Type.SERVER,
        status=ConfigurationItem.Status.LIVE,
        category="Infrastructure",
        subcategory="Application Server",
        hostname="argus-api-02",
        ip_address="10.10.10.11",
        management_ip_address="10.10.10.11",
        site_slug="dr-site",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Argus API DR",
        manufacturer="Dell",
        model="PowerEdge R650",
        os="Ubuntu",
        os_version="22.04 LTS",
        rack_position="R2-U10",
        prometheus_job="server",
        cpu="16 vCPU",
        memory="64 GB",
        storage="1.5 TB SSD",
        metadata={"tier": "app", "linkedeye_family": "server"},
    ),
    SeedAsset(
        external_id="seed:k8s-prod-cluster",
        name="k8s-prod-cluster",
        type=ConfigurationItem.Type.KUBERNETES_CLUSTER,
        status=ConfigurationItem.Status.LIVE,
        category="Platform",
        subcategory="Kubernetes",
        hostname="k8s-prod-cluster",
        ip_address="10.10.30.5",
        management_ip_address="10.10.30.5",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Production Kubernetes",
        manufacturer="VMware",
        model="vSphere Cluster",
        metadata={"node_count": 6, "linkedeye_family": "kubernetes"},
    ),
    SeedAsset(
        external_id="seed:postgres-primary-01",
        name="postgres-primary-01",
        type=ConfigurationItem.Type.DATABASE,
        status=ConfigurationItem.Status.LIVE,
        category="Data",
        subcategory="PostgreSQL Primary",
        hostname="postgres-primary-01",
        ip_address="10.10.40.20",
        management_ip_address="10.10.40.20",
        site_slug="production",
        team_name="Database Operations",
        owner_email="admin@argus.com",
        service_name="Argus PostgreSQL Primary",
        manufacturer="Dell",
        model="PowerEdge R550",
        os="Ubuntu",
        os_version="22.04 LTS",
        prometheus_job="postgres",
        cpu="8 vCPU",
        memory="32 GB",
        storage="2 TB NVMe",
        metadata={"replication_role": "primary", "linkedeye_family": "database"},
    ),
    SeedAsset(
        external_id="seed:postgres-replica-01",
        name="postgres-replica-01",
        type=ConfigurationItem.Type.DATABASE,
        status=ConfigurationItem.Status.LIVE,
        category="Data",
        subcategory="PostgreSQL Replica",
        hostname="postgres-replica-01",
        ip_address="10.10.40.21",
        management_ip_address="10.10.40.21",
        site_slug="dr-site",
        team_name="Database Operations",
        owner_email="admin@argus.com",
        service_name="Argus PostgreSQL Replica",
        manufacturer="Dell",
        model="PowerEdge R550",
        os="Ubuntu",
        os_version="22.04 LTS",
        prometheus_job="postgres",
        cpu="8 vCPU",
        memory="32 GB",
        storage="2 TB NVMe",
        metadata={"replication_role": "replica", "linkedeye_family": "database"},
    ),
    SeedAsset(
        external_id="seed:core-switch-01",
        name="core-switch-01",
        type=ConfigurationItem.Type.SWITCH,
        status=ConfigurationItem.Status.LIVE,
        category="Network",
        subcategory="Core Switch",
        hostname="core-switch-01",
        ip_address="10.10.0.2",
        management_ip_address="10.10.0.2",
        site_slug="production",
        team_name="Network Operations",
        owner_email="admin@argus.com",
        service_name="Core Network",
        manufacturer="Cisco",
        model="Nexus 93180YC-FX",
        prometheus_job="snmp",
        metadata={"layer": "L3", "linkedeye_family": "switch"},
    ),
    SeedAsset(
        external_id="seed:edge-router-01",
        name="edge-router-01",
        type=ConfigurationItem.Type.ROUTER,
        status=ConfigurationItem.Status.LIVE,
        category="Network",
        subcategory="WAN Router",
        hostname="edge-router-01",
        ip_address="10.10.0.1",
        management_ip_address="10.10.0.1",
        site_slug="production",
        team_name="Network Operations",
        owner_email="admin@argus.com",
        service_name="Edge Routing",
        manufacturer="Cisco",
        model="ASR 1001-X",
        prometheus_job="snmp",
        metadata={"uplink": "MPLS", "linkedeye_family": "router"},
    ),
    SeedAsset(
        external_id="seed:edge-firewall-01",
        name="edge-firewall-01",
        type=ConfigurationItem.Type.FIREWALL,
        status=ConfigurationItem.Status.LIVE,
        category="Security",
        subcategory="Perimeter Firewall",
        hostname="edge-firewall-01",
        ip_address="10.10.0.254",
        management_ip_address="10.10.0.254",
        site_slug="production",
        team_name="Network Operations",
        owner_email="admin@argus.com",
        service_name="Perimeter Security",
        manufacturer="Palo Alto",
        model="PA-3220",
        prometheus_job="snmp",
        metadata={"zone_count": 5, "linkedeye_family": "firewall"},
    ),
    SeedAsset(
        external_id="seed:distribution-network-01",
        name="distribution-network-01",
        type=ConfigurationItem.Type.NETWORK,
        status=ConfigurationItem.Status.LIVE,
        category="Network",
        subcategory="Distribution Network",
        hostname="distribution-network-01",
        ip_address="10.10.1.1",
        management_ip_address="10.10.1.1",
        site_slug="production",
        team_name="Network Operations",
        owner_email="admin@argus.com",
        service_name="Distribution Aggregation",
        manufacturer="Arista",
        model="7050SX3",
        prometheus_job="snmp",
        metadata={"linkedeye_family": "network"},
    ),
    SeedAsset(
        external_id="seed:lb-01",
        name="lb-01",
        type=ConfigurationItem.Type.LOAD_BALANCER,
        status=ConfigurationItem.Status.LIVE,
        category="Network",
        subcategory="ADC",
        hostname="lb-01",
        ip_address="10.10.15.20",
        management_ip_address="10.10.15.20",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Ingress Load Balancer",
        manufacturer="F5",
        model="BIG-IP VE",
        metadata={"virtual_servers": 12, "linkedeye_family": "load-balancer"},
    ),
    SeedAsset(
        external_id="seed:vm-jump-01",
        name="vm-jump-01",
        type=ConfigurationItem.Type.VM,
        status=ConfigurationItem.Status.LIVE,
        category="Infrastructure",
        subcategory="Jump Host",
        hostname="vm-jump-01",
        ip_address="10.10.60.15",
        management_ip_address="10.10.60.15",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Jump Host",
        manufacturer="VMware",
        model="Virtual Machine",
        os="Windows Server",
        os_version="2022",
        cpu="4 vCPU",
        memory="16 GB",
        storage="200 GB SSD",
        metadata={"linkedeye_family": "vm"},
    ),
    SeedAsset(
        external_id="seed:storage-san-01",
        name="storage-san-01",
        type=ConfigurationItem.Type.STORAGE,
        status=ConfigurationItem.Status.LIVE,
        category="Storage",
        subcategory="SAN",
        hostname="storage-san-01",
        ip_address="10.10.70.30",
        management_ip_address="10.10.70.30",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Primary Storage Array",
        manufacturer="NetApp",
        model="AFF A250",
        storage="50 TB",
        metadata={"linkedeye_family": "storage"},
    ),
    SeedAsset(
        external_id="seed:container-web-01",
        name="container-web-01",
        type=ConfigurationItem.Type.CONTAINER,
        status=ConfigurationItem.Status.LIVE,
        category="Platform",
        subcategory="Web Pod",
        hostname="container-web-01",
        ip_address="10.10.30.101",
        management_ip_address="10.10.30.101",
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Argus Web Pod",
        manufacturer="Docker",
        model="Container",
        metadata={"namespace": "argus-prod", "linkedeye_family": "container"},
    ),
    SeedAsset(
        external_id="seed:endpoint-laptop-01",
        name="endpoint-laptop-01",
        type=ConfigurationItem.Type.END_USER_DEVICE,
        status=ConfigurationItem.Status.LIVE,
        category="End User",
        subcategory="Laptop",
        hostname="endpoint-laptop-01",
        ip_address="10.10.80.40",
        management_ip_address="10.10.80.40",
        site_slug="production",
        team_name="Service Desk",
        owner_email="admin@argus.com",
        service_name="Admin Workstation",
        manufacturer="Lenovo",
        model="ThinkPad T14",
        os="Windows",
        os_version="11 Pro",
        metadata={"linkedeye_family": "computer"},
    ),
    SeedAsset(
        external_id="seed:ups-a01",
        name="ups-a01",
        type=ConfigurationItem.Type.UPS,
        status=ConfigurationItem.Status.LIVE,
        category="Power",
        subcategory="Rack UPS",
        hostname="ups-a01",
        ip_address="10.10.90.10",
        management_ip_address="10.10.90.10",
        site_slug="production",
        team_name="Facilities",
        owner_email="admin@argus.com",
        service_name="Rack A UPS",
        manufacturer="APC",
        model="Smart-UPS 3000",
        metadata={"linkedeye_family": "ups"},
    ),
    SeedAsset(
        external_id="seed:printer-noc-01",
        name="printer-noc-01",
        type=ConfigurationItem.Type.PRINTER,
        status=ConfigurationItem.Status.LIVE,
        category="Peripherals",
        subcategory="Laser Printer",
        hostname="printer-noc-01",
        ip_address="10.10.81.25",
        management_ip_address="10.10.81.25",
        site_slug="production",
        team_name="Service Desk",
        owner_email="admin@argus.com",
        service_name="NOC Printer",
        manufacturer="HP",
        model="LaserJet Enterprise",
        metadata={"linkedeye_family": "printer"},
    ),
    SeedAsset(
        external_id="seed:monitor-noc-01",
        name="monitor-noc-01",
        type=ConfigurationItem.Type.MONITOR,
        status=ConfigurationItem.Status.LIVE,
        category="Peripherals",
        subcategory="NOC Display",
        hostname="monitor-noc-01",
        ip_address=None,
        management_ip_address=None,
        site_slug="production",
        team_name="Service Desk",
        owner_email="admin@argus.com",
        service_name="NOC Wall Monitor",
        manufacturer="Samsung",
        model="QM75R",
        monitoring_enabled=False,
        metadata={"linkedeye_family": "monitor"},
    ),
    SeedAsset(
        external_id="seed:phone-helpdesk-01",
        name="phone-helpdesk-01",
        type=ConfigurationItem.Type.PHONE,
        status=ConfigurationItem.Status.LIVE,
        category="Telephony",
        subcategory="Desk Phone",
        hostname="phone-helpdesk-01",
        ip_address="10.10.82.30",
        management_ip_address="10.10.82.30",
        site_slug="production",
        team_name="Service Desk",
        owner_email="admin@argus.com",
        service_name="Helpdesk Phone",
        manufacturer="Cisco",
        model="8845",
        metadata={"linkedeye_family": "phone"},
    ),
    SeedAsset(
        external_id="seed:peripheral-kvm-01",
        name="peripheral-kvm-01",
        type=ConfigurationItem.Type.PERIPHERAL,
        status=ConfigurationItem.Status.LIVE,
        category="Peripherals",
        subcategory="KVM Console",
        hostname="peripheral-kvm-01",
        ip_address=None,
        management_ip_address=None,
        site_slug="production",
        team_name="Facilities",
        owner_email="admin@argus.com",
        service_name="KVM Console",
        manufacturer="Aten",
        model="KN1132V",
        monitoring_enabled=False,
        metadata={"linkedeye_family": "peripheral"},
    ),
    SeedAsset(
        external_id="seed:rack-a01",
        name="rack-a01",
        type=ConfigurationItem.Type.RACK_UNIT,
        status=ConfigurationItem.Status.LIVE,
        category="Rack",
        subcategory="42U Rack",
        hostname="rack-a01",
        ip_address=None,
        management_ip_address=None,
        site_slug="production",
        team_name="Facilities",
        owner_email="admin@argus.com",
        service_name="Rack A01",
        manufacturer="APC",
        model="NetShelter SX",
        monitoring_enabled=False,
        metadata={"linkedeye_family": "rack"},
    ),
    SeedAsset(
        external_id="seed:pdu-a01",
        name="pdu-a01",
        type=ConfigurationItem.Type.PDU,
        status=ConfigurationItem.Status.LIVE,
        category="Power",
        subcategory="Switched PDU",
        hostname="pdu-a01",
        ip_address="10.10.90.20",
        management_ip_address="10.10.90.20",
        site_slug="production",
        team_name="Facilities",
        owner_email="admin@argus.com",
        service_name="Rack A PDU",
        manufacturer="APC",
        model="AP8959",
        metadata={"linkedeye_family": "pdu"},
    ),
    SeedAsset(
        external_id="seed:enclosure-a01",
        name="enclosure-a01",
        type=ConfigurationItem.Type.ENCLOSURE,
        status=ConfigurationItem.Status.LIVE,
        category="Rack",
        subcategory="Blade Enclosure",
        hostname="enclosure-a01",
        ip_address="10.10.90.30",
        management_ip_address="10.10.90.30",
        site_slug="production",
        team_name="Facilities",
        owner_email="admin@argus.com",
        service_name="Blade Enclosure",
        manufacturer="HPE",
        model="Synergy 12000",
        metadata={"linkedeye_family": "enclosure"},
    ),
    SeedAsset(
        external_id="seed:cable-a01",
        name="cable-a01",
        type=ConfigurationItem.Type.CABLE,
        status=ConfigurationItem.Status.LIVE,
        category="Rack",
        subcategory="Fiber Uplink",
        hostname="cable-a01",
        ip_address=None,
        management_ip_address=None,
        site_slug="production",
        team_name="Facilities",
        owner_email="admin@argus.com",
        service_name="Rack Fiber Uplink",
        manufacturer="Corning",
        model="OM4 Fiber",
        monitoring_enabled=False,
        metadata={"linkedeye_family": "cable"},
    ),
    SeedAsset(
        external_id="seed:simcard-iot-01",
        name="simcard-iot-01",
        type=ConfigurationItem.Type.SIMCARD,
        status=ConfigurationItem.Status.LIVE,
        category="Connectivity",
        subcategory="4G Backup SIM",
        hostname="simcard-iot-01",
        ip_address=None,
        management_ip_address=None,
        site_slug="production",
        team_name="Network Operations",
        owner_email="admin@argus.com",
        service_name="WAN Backup SIM",
        manufacturer="Airtel",
        model="Enterprise SIM",
        monitoring_enabled=False,
        metadata={"linkedeye_family": "simcard"},
    ),
    SeedAsset(
        external_id="seed:argus-software-keycloak",
        name="argus-software-keycloak",
        type=ConfigurationItem.Type.SOFTWARE,
        status=ConfigurationItem.Status.LIVE,
        category="Software",
        subcategory="Identity Provider",
        hostname="argus-software-keycloak",
        ip_address=None,
        management_ip_address=None,
        site_slug="production",
        team_name="Platform Operations",
        owner_email="admin@argus.com",
        service_name="Keycloak",
        manufacturer="Red Hat",
        model="Keycloak 25",
        monitoring_enabled=False,
        metadata={"linkedeye_family": "software"},
    ),
)


SEED_RELATIONSHIPS = [
    ("seed:argus-web-01", "seed:lb-01", AssetRelationship.RelationshipType.DEPENDS_ON, "fronted by"),
    ("seed:lb-01", "seed:argus-api-01", AssetRelationship.RelationshipType.CONNECTS_TO, "routes to"),
    ("seed:lb-01", "seed:argus-api-02", AssetRelationship.RelationshipType.CONNECTS_TO, "routes to"),
    ("seed:argus-api-01", "seed:postgres-primary-01", AssetRelationship.RelationshipType.DEPENDS_ON, "reads/writes"),
    ("seed:argus-api-02", "seed:postgres-replica-01", AssetRelationship.RelationshipType.DEPENDS_ON, "reads from"),
    ("seed:container-web-01", "seed:k8s-prod-cluster", AssetRelationship.RelationshipType.RUNS_ON, "runs on"),
    ("seed:k8s-prod-cluster", "seed:core-switch-01", AssetRelationship.RelationshipType.CONNECTS_TO, "uplink"),
    ("seed:core-switch-01", "seed:edge-router-01", AssetRelationship.RelationshipType.CONNECTS_TO, "transit"),
    ("seed:edge-router-01", "seed:edge-firewall-01", AssetRelationship.RelationshipType.CONNECTS_TO, "perimeter"),
]


SEED_PORT_CONNECTIONS = [
    {
        "key": "seed:port:api01:core",
        "source_asset": "seed:argus-api-01",
        "target_asset": "seed:core-switch-01",
        "source_port": "eth0",
        "destination_port": "Gi1/0/10",
        "status": AssetPortConnection.Status.ACTIVE,
    },
    {
        "key": "seed:port:api02:core",
        "source_asset": "seed:argus-api-02",
        "target_asset": "seed:core-switch-01",
        "source_port": "eth0",
        "destination_port": "Gi1/0/11",
        "status": AssetPortConnection.Status.ACTIVE,
    },
    {
        "key": "seed:port:core:router",
        "source_asset": "seed:core-switch-01",
        "target_asset": "seed:edge-router-01",
        "source_port": "Te1/1/1",
        "destination_port": "xe-0/0/0",
        "status": AssetPortConnection.Status.ACTIVE,
    },
]


def _ensure_team(org: Organization, name: str, manager: User | None) -> Team:
    team_email = f"{name.lower().replace(' ', '.')}@argus.local"
    team, _ = Team.objects.get_or_create(
        organization=org,
        name=name,
        defaults={
            "description": f"{name} team",
            "email": team_email.replace("..", "."),
            "manager": manager,
            "is_active": True,
        },
    )
    if manager:
        TeamMember.objects.get_or_create(team=team, user=manager, defaults={"role": Team.MemberRole.LEAD})
    return team


def _ensure_catalog(org: Organization) -> None:
    for category, names in SEED_CATALOG.items():
        for name in names:
            AssetCatalog.objects.get_or_create(
                organization=org,
                category=category,
                name=name,
                defaults={"is_active": True},
            )


def _site_defaults(site_def: dict) -> dict:
    defaults = dict(site_def)
    if settings.ARGUS_DEFAULT_PROMETHEUS_URL:
        defaults["prometheus_url"] = settings.ARGUS_DEFAULT_PROMETHEUS_URL
    if settings.ARGUS_DEFAULT_GRAFANA_URL:
        defaults["grafana_url"] = settings.ARGUS_DEFAULT_GRAFANA_URL
    if settings.ARGUS_DEFAULT_REDIS_URL:
        defaults["redis_url"] = settings.ARGUS_DEFAULT_REDIS_URL
    if settings.ARGUS_DEFAULT_ENTITY_HOST:
        defaults["entity_host"] = settings.ARGUS_DEFAULT_ENTITY_HOST
    if settings.ARGUS_DEFAULT_ENTITY_PORT:
        defaults["entity_port"] = int(settings.ARGUS_DEFAULT_ENTITY_PORT)
    return defaults


def _ensure_sites(org: Organization) -> dict[str, AssetSite]:
    sites: dict[str, AssetSite] = {}
    for site_def in SEED_SITES:
        site, _ = AssetSite.objects.update_or_create(
            organization=org,
            slug=site_def["slug"],
            defaults=_site_defaults(site_def),
        )
        sites[site.slug] = site
    return sites


def _ensure_management_endpoints(asset: ConfigurationItem) -> None:
    if not asset.management_ip_address and not asset.ip_address:
        return

    management_ip = asset.management_ip_address or asset.ip_address
    protocol = None
    port = None

    if asset.type in {ConfigurationItem.Type.SERVER, ConfigurationItem.Type.VM, ConfigurationItem.Type.DATABASE}:
        protocol = AssetManagementEndpoint.Protocol.NODE_EXPORTER
        port = 9100
    elif asset.type in {
        ConfigurationItem.Type.SWITCH,
        ConfigurationItem.Type.ROUTER,
        ConfigurationItem.Type.FIREWALL,
        ConfigurationItem.Type.NETWORK,
    }:
        protocol = AssetManagementEndpoint.Protocol.SNMP
        port = 161
    elif asset.type in {ConfigurationItem.Type.APPLICATION, ConfigurationItem.Type.LOAD_BALANCER}:
        protocol = AssetManagementEndpoint.Protocol.API
        port = 443

    if protocol is None:
        return

    AssetManagementEndpoint.objects.update_or_create(
        configuration_item=asset,
        protocol=protocol,
        management_ip=management_ip,
        defaults={"port": port, "is_active": True},
    )


def bootstrap_inventory_for_organization(org: Organization, *, force: bool = False) -> dict[str, int]:
    users_by_email = {user.email: user for user in User.objects.filter(organization=org).exclude(email="")}
    manager = users_by_email.get("admin@argus.com") or next(iter(users_by_email.values()), None)

    sites = _ensure_sites(org)
    _ensure_catalog(org)

    teams = {
        name: _ensure_team(org, name, manager)
        for name in (
            "Platform Operations",
            "Network Operations",
            "Database Operations",
            "Service Desk",
            "Facilities",
        )
    }

    created_assets = 0
    updated_assets = 0
    assets_by_external_id: dict[str, ConfigurationItem] = {}

    for asset_def in SEED_ASSETS:
        defaults = {
            "name": asset_def.name,
            "type": asset_def.type,
            "status": asset_def.status,
            "category": asset_def.category,
            "subcategory": asset_def.subcategory,
            "description": "LinkedEye parity CMDB seed for Argus demo inventory.",
            "hostname": asset_def.hostname,
            "ip_address": asset_def.ip_address,
            "management_ip_address": asset_def.management_ip_address,
            "site": sites[asset_def.site_slug],
            "support_group": teams[asset_def.team_name],
            "owner": users_by_email.get(asset_def.owner_email) if asset_def.owner_email else None,
            "service_name": asset_def.service_name,
            "manufacturer": asset_def.manufacturer,
            "model": asset_def.model,
            "os": asset_def.os,
            "os_version": asset_def.os_version,
            "rack_position": asset_def.rack_position,
            "prometheus_job": asset_def.prometheus_job,
            "monitoring_enabled": asset_def.monitoring_enabled,
            "location": asset_def.location or sites[asset_def.site_slug].location,
            "environment": sites[asset_def.site_slug].environment,
            "cpu": asset_def.cpu,
            "memory": asset_def.memory,
            "storage": asset_def.storage,
            "metadata": asset_def.metadata or {},
        }

        asset, created = ConfigurationItem.objects.update_or_create(
            organization=org,
            external_id=asset_def.external_id,
            defaults=defaults,
        )
        assets_by_external_id[asset_def.external_id] = asset
        if created:
            created_assets += 1
        else:
            updated_assets += 1

        _ensure_management_endpoints(asset)

    created_relationships = 0
    for source_key, target_key, rel_type, label in SEED_RELATIONSHIPS:
        _, created = AssetRelationship.objects.get_or_create(
            organization=org,
            source_ci=assets_by_external_id[source_key],
            target_ci=assets_by_external_id[target_key],
            relationship_type=rel_type,
            defaults={"label": label, "created_by": manager},
        )
        if created:
            created_relationships += 1

    created_port_connections = 0
    for row in SEED_PORT_CONNECTIONS:
        source = assets_by_external_id[row["source_asset"]]
        target = assets_by_external_id[row["target_asset"]]
        _, created = AssetPortConnection.objects.update_or_create(
            organization=org,
            source_ci=source,
            target_ci=target,
            source_port=row["source_port"],
            destination_port=row["destination_port"],
            defaults={
                "source_name": source.name,
                "source_ip": source.ip_address,
                "destination_name": target.name,
                "destination_ip": target.ip_address,
                "status": row["status"],
                "metadata": {"seed_key": row["key"]},
            },
        )
        if created:
            created_port_connections += 1

    if force:
        # Backfill runtime integration defaults from environment-backed settings.
        for site in sites.values():
            changed_fields: list[str] = []
            if settings.ARGUS_DEFAULT_PROMETHEUS_URL and not site.prometheus_url:
                site.prometheus_url = settings.ARGUS_DEFAULT_PROMETHEUS_URL
                changed_fields.append("prometheus_url")
            if settings.ARGUS_DEFAULT_GRAFANA_URL and not site.grafana_url:
                site.grafana_url = settings.ARGUS_DEFAULT_GRAFANA_URL
                changed_fields.append("grafana_url")
            if settings.ARGUS_DEFAULT_REDIS_URL and not site.redis_url:
                site.redis_url = settings.ARGUS_DEFAULT_REDIS_URL
                changed_fields.append("redis_url")
            if settings.ARGUS_DEFAULT_ENTITY_HOST and not site.entity_host:
                site.entity_host = settings.ARGUS_DEFAULT_ENTITY_HOST
                changed_fields.append("entity_host")
            if settings.ARGUS_DEFAULT_ENTITY_PORT and not site.entity_port:
                site.entity_port = int(settings.ARGUS_DEFAULT_ENTITY_PORT)
                changed_fields.append("entity_port")
            if changed_fields:
                site.save(update_fields=changed_fields + ["updated_at"])

    return {
        "assets": len(SEED_ASSETS),
        "assets_created": created_assets,
        "assets_updated": updated_assets,
        "catalog_items": sum(len(items) for items in SEED_CATALOG.values()),
        "teams": len(teams),
        "relationships_created": created_relationships,
        "port_connections_created": created_port_connections,
    }


def bootstrap_inventory_if_demo(org: Organization) -> None:
    asset_count = ConfigurationItem.objects.filter(organization=org).count()
    if asset_count == 0 or (org.slug in {"demo-org", "default-organization"} and asset_count < 8):
        bootstrap_inventory_for_organization(org)
