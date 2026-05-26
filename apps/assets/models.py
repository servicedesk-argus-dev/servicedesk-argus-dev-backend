import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.organizations.models import Organization

User = get_user_model()


class ActiveCIManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(status=ConfigurationItem.Status.DECOMMISSIONED)


class ConfigurationItem(models.Model):
    class Type(models.TextChoices):
        SERVER = "SERVER", "Server"
        KUBERNETES_CLUSTER = "KUBERNETES_CLUSTER", "Kubernetes Cluster"
        DATABASE = "DATABASE", "Database"
        APPLICATION = "APPLICATION", "Application"
        NETWORK = "NETWORK", "Network"
        NETWORK_DEVICE = "NETWORK_DEVICE", "Network Device"
        SWITCH = "SWITCH", "Switch"
        ROUTER = "ROUTER", "Router"
        FIREWALL = "FIREWALL", "Firewall"
        STORAGE = "STORAGE", "Storage"
        CONTAINER = "CONTAINER", "Container"
        VM = "VM", "Virtual Machine"
        LOAD_BALANCER = "LOAD_BALANCER", "Load Balancer"
        SOFTWARE = "SOFTWARE", "Software"
        END_USER_DEVICE = "END_USER_DEVICE", "End User Device"
        MONITOR = "MONITOR", "Monitor"
        PERIPHERAL = "PERIPHERAL", "Peripheral"
        SIMCARD = "SIMCARD", "SIM Card"
        PHONE = "PHONE", "Phone"
        PRINTER = "PRINTER", "Printer"
        RACK_UNIT = "RACK_UNIT", "Rack Unit"
        PDU = "PDU", "Power Distribution Unit"
        ENCLOSURE = "ENCLOSURE", "Enclosure"
        CABLE = "CABLE", "Cable"
        UPS = "UPS", "UPS"

    class Status(models.TextChoices):
        LIVE = "LIVE", "Live"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        DECOMMISSIONED = "DECOMMISSIONED", "Decommissioned"
        PLANNED = "PLANNED", "Planned"
        IN_STOCK = "IN_STOCK", "In Stock"
        RESERVED = "RESERVED", "Reserved"
        DISPOSED = "DISPOSED", "Disposed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.SERVER, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LIVE, db_index=True)
    
    category = models.CharField(max_length=100, blank=True, null=True)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    template = models.CharField(max_length=100, blank=True, null=True)
    network_type = models.CharField(max_length=50, blank=True, null=True)
    switch_type = models.CharField(max_length=50, blank=True, null=True)
    firewall_type = models.CharField(max_length=50, blank=True, null=True)
    router_type = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    serial_number = models.CharField(max_length=255, blank=True, null=True)
    asset_tag = models.CharField(max_length=255, blank=True, null=True)
    manufacturer = models.CharField(max_length=255, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    version = models.CharField(max_length=255, blank=True, null=True)
    
    location = models.CharField(max_length=255, blank=True, null=True)
    rack_position = models.CharField(max_length=100, blank=True, null=True)
    data_center = models.CharField(max_length=255, blank=True, null=True)
    
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    physical_ip_address = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=255, blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    fqdn = models.CharField(max_length=255, blank=True, null=True)
    
    cpu = models.CharField(max_length=255, blank=True, null=True)
    memory = models.CharField(max_length=255, blank=True, null=True)
    storage = models.CharField(max_length=255, blank=True, null=True)
    
    os = models.CharField(max_length=255, blank=True, null=True)
    os_version = models.CharField(max_length=255, blank=True, null=True)
    service_name = models.CharField(max_length=255, blank=True, null=True)
    management_ip_address = models.GenericIPAddressField(blank=True, null=True)
    environment = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    owner = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_assets')
    support_group = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='supported_assets')
    
    vendor = models.CharField(max_length=255, blank=True, null=True)
    purchase_date = models.DateField(blank=True, null=True)
    warranty_expiry = models.DateField(blank=True, null=True)
    end_of_life = models.DateField(blank=True, null=True)
    end_of_support = models.DateField(blank=True, null=True)
    
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    monthly_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    cost_center = models.CharField(max_length=100, blank=True, null=True)
    
    monitoring_enabled = models.BooleanField(default=True)
    metrics_management_interfaces = models.BooleanField(default=False)
    prometheus_job = models.CharField(max_length=255, blank=True, null=True)
    grafana_dashboard = models.CharField(max_length=255, blank=True, null=True)
    loki_labels = models.JSONField(blank=True, null=True)
    health_score = models.PositiveSmallIntegerField(blank=True, null=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    external_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='assets')
    site = models.ForeignKey(
        'assets.AssetSite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configuration_items',
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveCIManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "configuration_items"
        ordering = ["name"]
        default_manager_name = "objects"
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["hostname"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["organization", "type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.type})"

    def delete(self, *args, **kwargs):
        raise NotImplementedError(
            "ConfigurationItems cannot be hard deleted. Set status to DECOMMISSIONED instead."
        )


class ConfigurationItemHistory(models.Model):
    class ChangeSource(models.TextChoices):
        USER = "user", "User"
        WORKER = "worker", "Worker"
        IMPORT = "import", "Import"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration_item = models.ForeignKey(
        ConfigurationItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_entries",
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="configuration_item_history")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configuration_item_history_entries",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    change_source = models.CharField(
        max_length=20,
        choices=ChangeSource.choices,
        default=ChangeSource.SYSTEM,
    )
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)

    class Meta:
        db_table = "configuration_item_history"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.configuration_item_id} {self.field_name} @ {self.changed_at.isoformat()}"


class AssetSite(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DEGRADED = "DEGRADED", "Degraded"
        OFFLINE = "OFFLINE", "Offline"
        RETIRED = "RETIRED", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='asset_sites')
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=140)
    environment = models.CharField(max_length=100, default="Production", db_index=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=120, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    entity_host = models.CharField(max_length=255, blank=True, null=True)
    entity_port = models.PositiveIntegerField(blank=True, null=True)
    entity_secure = models.BooleanField(default=False)
    websocket_host = models.CharField(max_length=255, blank=True, null=True)
    websocket_port = models.PositiveIntegerField(blank=True, null=True)
    websocket_secure = models.BooleanField(default=False)

    redis_url = models.CharField(max_length=500, blank=True, null=True)
    prometheus_url = models.URLField(max_length=500, blank=True, null=True)
    grafana_url = models.URLField(max_length=500, blank=True, null=True)
    redmine_url = models.URLField(max_length=500, blank=True, null=True)
    incident_url = models.URLField(max_length=500, blank=True, null=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_sites"
        ordering = ["name"]
        unique_together = ["organization", "slug"]

    def __str__(self):
        return f"{self.name} ({self.environment})"


class AssetCatalog(models.Model):
    class Category(models.TextChoices):
        SERVER_TYPE = "SERVER_TYPE", "Server Type"
        SERVER_OS = "SERVER_OS", "Server OS"
        SERVER_SOFTWARE = "SERVER_SOFTWARE", "Server Software"
        SERVER_NIC = "SERVER_NIC", "Server NIC"
        SWITCH_LAYER = "SWITCH_LAYER", "Switch Layer"
        SWITCH_MODEL = "SWITCH_MODEL", "Switch Model"
        FIREWALL_TYPE = "FIREWALL_TYPE", "Firewall Type"
        FIREWALL_MODEL = "FIREWALL_MODEL", "Firewall Model"
        ROUTER_TYPE = "ROUTER_TYPE", "Router Type"
        ROUTER_MODEL = "ROUTER_MODEL", "Router Model"
        SOFTWARE = "SOFTWARE", "Software"
        APPLICATION = "APPLICATION", "Application"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='asset_catalog_items',
    )
    category = models.CharField(max_length=40, choices=Category.choices, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_catalog"
        ordering = ["category", "name"]
        unique_together = ["organization", "category", "name"]

    def __str__(self):
        return f"{self.category}: {self.name}"


class AssetManagementEndpoint(models.Model):
    class Protocol(models.TextChoices):
        IDRAC = "IDRAC", "iDRAC"
        ILO = "ILO", "iLO"
        SNMP = "SNMP", "SNMP"
        NODE_EXPORTER = "NODE_EXPORTER", "Node Exporter"
        WINDOWS_EXPORTER = "WINDOWS_EXPORTER", "Windows Exporter"
        NGINX_EXPORTER = "NGINX_EXPORTER", "Nginx Exporter"
        REDFISH = "REDFISH", "Redfish"
        SSH = "SSH", "SSH"
        WINRM = "WINRM", "WinRM"
        API = "API", "API"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration_item = models.ForeignKey(
        ConfigurationItem,
        on_delete=models.CASCADE,
        related_name='management_endpoints',
    )
    protocol = models.CharField(max_length=40, choices=Protocol.choices, db_index=True)
    management_ip = models.GenericIPAddressField(blank=True, null=True)
    ilo_ip = models.GenericIPAddressField(blank=True, null=True)
    port = models.PositiveIntegerField(blank=True, null=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    secret_ref = models.CharField(max_length=255, blank=True, null=True)
    threshold = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_management_endpoints"
        ordering = ["protocol", "management_ip"]

    def __str__(self):
        return f"{self.configuration_item.name} {self.protocol}"


class AssetRelationship(models.Model):
    class RelationshipType(models.TextChoices):
        DEPENDS_ON = "DEPENDS_ON", "Depends On"
        CONNECTS_TO = "CONNECTS_TO", "Connects To"
        HOSTS = "HOSTS", "Hosts"
        RUNS_ON = "RUNS_ON", "Runs On"
        MANAGES = "MANAGES", "Manages"
        MONITORS = "MONITORS", "Monitors"
        RELATED_TO = "RELATED_TO", "Related To"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='asset_relationships')
    source_ci = models.ForeignKey(ConfigurationItem, on_delete=models.CASCADE, related_name='outgoing_relationships')
    target_ci = models.ForeignKey(ConfigurationItem, on_delete=models.CASCADE, related_name='incoming_relationships')
    relationship_type = models.CharField(max_length=30, choices=RelationshipType.choices, default=RelationshipType.RELATED_TO, db_index=True)
    label = models.CharField(max_length=255, blank=True, null=True)
    source_port = models.CharField(max_length=100, blank=True, null=True)
    target_port = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_asset_relationships')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_relationships"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "relationship_type"]),
            models.Index(fields=["source_ci", "target_ci"]),
        ]

    def __str__(self):
        return f"{self.source_ci} {self.relationship_type} {self.target_ci}"


class AssetPortConnection(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PLANNED = "PLANNED", "Planned"
        DOWN = "DOWN", "Down"
        RETIRED = "RETIRED", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='asset_port_connections')
    source_ci = models.ForeignKey(ConfigurationItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='source_port_connections')
    target_ci = models.ForeignKey(ConfigurationItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='target_port_connections')
    source_modal = models.CharField(max_length=255, blank=True, null=True)
    source_ip = models.GenericIPAddressField(blank=True, null=True)
    source_port = models.CharField(max_length=100)
    source_name = models.CharField(max_length=255, blank=True, null=True)
    destination_modal = models.CharField(max_length=255, blank=True, null=True)
    destination_ip = models.GenericIPAddressField(blank=True, null=True)
    destination_port = models.CharField(max_length=100)
    destination_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_port_connections"
        ordering = ["source_name", "source_port"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["source_ip"]),
            models.Index(fields=["destination_ip"]),
        ]

    def __str__(self):
        return f"{self.source_name or self.source_ip}:{self.source_port} -> {self.destination_name or self.destination_ip}:{self.destination_port}"


class AssetDiscoveryResult(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        ACCEPTED = "ACCEPTED", "Accepted"
        IGNORED = "IGNORED", "Ignored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='asset_discovery_results')
    site = models.ForeignKey(AssetSite, on_delete=models.SET_NULL, null=True, blank=True, related_name='discovery_results')
    scan_range_start = models.GenericIPAddressField(blank=True, null=True)
    scan_range_end = models.GenericIPAddressField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    asset_type = models.CharField(max_length=30, choices=ConfigurationItem.Type.choices, default=ConfigurationItem.Type.SERVER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    discovered_data = models.JSONField(default=dict, blank=True)
    accepted_ci = models.ForeignKey(ConfigurationItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_discovery_results')
    discovered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_discovery_results"
        ordering = ["-discovered_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "ip_address"]),
        ]

    def __str__(self):
        return f"{self.ip_address} ({self.status})"


class AssetOnboardingRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        VALIDATED = "VALIDATED", "Validated"
        ONBOARDED = "ONBOARDED", "Onboarded"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='asset_onboarding_records')
    configuration_item = models.ForeignKey(ConfigurationItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='onboarding_records')
    discovery_result = models.ForeignKey(AssetDiscoveryResult, on_delete=models.SET_NULL, null=True, blank=True, related_name='onboarding_records')
    site = models.ForeignKey(AssetSite, on_delete=models.SET_NULL, null=True, blank=True, related_name='onboarding_records')
    select_host = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    sub_ip_address = models.GenericIPAddressField(blank=True, null=True)
    server_type = models.CharField(max_length=255, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    service_name = models.CharField(max_length=255, blank=True, null=True)
    path_host = models.CharField(max_length=255, blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    physical_ip_address = models.GenericIPAddressField(blank=True, null=True)
    main_ip_address = models.GenericIPAddressField(blank=True, null=True)
    raw_json = models.JSONField(default=dict, blank=True)
    raw_text = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    error_message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_onboarding_records')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_onboarding_records"
        ordering = ["-created_at"]

    def __str__(self):
        return self.hostname or self.service_name or str(self.id)


class AssetMetricsManagement(models.Model):
    """
    Model for storing metrics and management interfaces configuration
    for ILO, IDRAC, Node Exporter, and Windows Exporter.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration_item = models.ForeignKey(
        ConfigurationItem,
        on_delete=models.CASCADE,
        related_name='metrics_management',
    )
    
    # ILO Configuration
    ilo_enabled = models.BooleanField(default=False)
    ilo_username = models.CharField(max_length=255, blank=True, null=True)
    ilo_password = models.CharField(max_length=255, blank=True, null=True)
    ilo_ip = models.GenericIPAddressField(blank=True, null=True)
    
    # IDRAC Configuration
    idrac_enabled = models.BooleanField(default=False)
    idrac_port = models.PositiveIntegerField(blank=True, null=True)
    
    # Node Exporter Configuration
    node_exporter_enabled = models.BooleanField(default=False)
    node_exporter_port = models.PositiveIntegerField(blank=True, null=True)
    
    # Windows Exporter Configuration
    windows_exporter_enabled = models.BooleanField(default=False)
    windows_exporter_port = models.PositiveIntegerField(blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_metrics_management"
        verbose_name = "Asset Metrics Management"
        verbose_name_plural = "Asset Metrics Management"

    def __str__(self):
        return f"{self.configuration_item.name} - Metrics Management"


class AssetSNMPConfiguration(models.Model):
    """
    Model for storing SNMP configuration.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration_item = models.ForeignKey(
        ConfigurationItem,
        on_delete=models.CASCADE,
        related_name='snmp_configurations',
    )
    
    snmp_enabled = models.BooleanField(default=False)
    snmp_version = models.CharField(max_length=10, blank=True, null=True)
    snmp_community_string = models.CharField(max_length=255, blank=True, null=True)
    snmp_username = models.CharField(max_length=255, blank=True, null=True)
    snmp_security_level = models.CharField(max_length=50, blank=True, null=True)
    snmp_auth_method = models.CharField(max_length=50, blank=True, null=True)
    snmp_auth_password = models.CharField(max_length=255, blank=True, null=True)
    snmp_privacy_method = models.CharField(max_length=50, blank=True, null=True)
    snmp_privacy_password = models.CharField(max_length=255, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_snmp_configurations"
        verbose_name = "Asset SNMP Configuration"
        verbose_name_plural = "Asset SNMP Configurations"

    def __str__(self):
        return f"{self.configuration_item.name} - SNMP Configuration"
