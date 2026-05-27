from rest_framework import serializers
from .models import (
    AssetCatalog,
    AssetDiscoveryResult,
    AssetManagementEndpoint,
    AssetMetricsManagement,
    AssetOnboardingRecord,
    AssetPortConnection,
    AssetRelationship,
    AssetSNMPConfiguration,
    AssetSite,
    ConfigurationItem,
)
from .validators import validate_metrics_management_interfaces, validate_network_type_fields
from apps.accounts.serializers import UserSerializer
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer


CAMEL_TO_SNAKE = {
    'serialNumber': 'serial_number',
    'assetTag': 'asset_tag',
    'rackPosition': 'rack_position',
    'dataCenter': 'data_center',
    'ipAddress': 'ip_address',
    'physicalIpAddress': 'physical_ip_address',
    'macAddress': 'mac_address',
    'osVersion': 'os_version',
    'serviceName': 'service_name',
    'managementIpAddress': 'management_ip_address',
    'ownerId': 'owner',
    'supportGroupId': 'support_group',
    'siteId': 'site',
    'purchaseDate': 'purchase_date',
    'warrantyExpiry': 'warranty_expiry',
    'endOfLife': 'end_of_life',
    'endOfSupport': 'end_of_support',
    'purchaseCost': 'purchase_cost',
    'monthlyCost': 'monthly_cost',
    'costCenter': 'cost_center',
    'monitoringEnabled': 'monitoring_enabled',
    'metricsManagementInterfaces': 'metrics_management_interfaces',
    'prometheusJob': 'prometheus_job',
    'grafanaDashboard': 'grafana_dashboard',
    'lokiLabels': 'loki_labels',
    'healthScore': 'health_score',
    'lastSeenAt': 'last_seen_at',
    'externalId': 'external_id',
    'networkType': 'network_type',
    'switchType': 'switch_type',
    'firewallType': 'firewall_type',
    'routerType': 'router_type',
}


class CamelCaseInputMixin:
    camel_to_snake = CAMEL_TO_SNAKE

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        for camel_key, snake_key in self.camel_to_snake.items():
            if camel_key in data and snake_key not in data:
                data[snake_key] = data[camel_key]
        return super().to_internal_value(data)


class ConfigurationItemSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    support_group = serializers.SerializerMethodField()
    site = serializers.SerializerMethodField()
    organization = OrganizationSerializer(read_only=True)
    metrics_management = serializers.SerializerMethodField()
    snmp_configurations = serializers.SerializerMethodField()

    class Meta:
        model = ConfigurationItem
        fields = [
            'id', 'name', 'type', 'status', 'category', 'subcategory', 'template',
            'network_type', 'switch_type', 'firewall_type', 'router_type', 'description',
            'serial_number', 'asset_tag', 'manufacturer', 'model', 'version',
            'location', 'rack_position', 'data_center', 'ip_address', 'physical_ip_address',
            'mac_address', 'hostname', 'fqdn', 'cpu', 'memory', 'storage', 'os', 'os_version',
            'service_name', 'management_ip_address', 'environment',
            'owner', 'support_group', 'vendor', 'purchase_date', 'warranty_expiry',
            'end_of_life', 'end_of_support', 'purchase_cost', 'monthly_cost',
            'cost_center', 'monitoring_enabled', 'metrics_management_interfaces',
            'prometheus_job', 'grafana_dashboard',
            'loki_labels', 'health_score', 'last_seen_at', 'external_id', 'metadata',
            'site', 'organization', 'created_at', 'updated_at',
            'metrics_management', 'snmp_configurations'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_support_group(self, obj):
        if obj.support_group:
            return {'id': str(obj.support_group.id), 'name': obj.support_group.name}
        return None

    def get_site(self, obj):
        if obj.site:
            return {'id': str(obj.site.id), 'name': obj.site.name, 'environment': obj.site.environment}
        return None

    def get_metrics_management(self, obj):
        metrics = obj.metrics_management.first()
        if metrics:
            return AssetMetricsManagementSerializer(metrics).data
        return None

    def get_snmp_configurations(self, obj):
        snmp = obj.snmp_configurations.first()
        if snmp:
            return AssetSNMPConfigurationSerializer(snmp).data
        return None


class ConfigurationItemCreateSerializer(CamelCaseInputMixin, serializers.ModelSerializer):
    class Meta:
        model = ConfigurationItem
        fields = [
            'name', 'type', 'status', 'category', 'subcategory', 'template',
            'network_type', 'switch_type', 'firewall_type', 'router_type', 'description',
            'serial_number', 'asset_tag', 'manufacturer', 'model', 'version',
            'location', 'rack_position', 'data_center', 'ip_address', 'physical_ip_address',
            'mac_address', 'hostname', 'fqdn', 'cpu', 'memory', 'storage', 'os', 'os_version',
            'service_name', 'management_ip_address', 'environment',
            'owner', 'support_group', 'vendor', 'purchase_date', 'warranty_expiry',
            'end_of_life', 'end_of_support', 'purchase_cost', 'monthly_cost',
            'cost_center', 'monitoring_enabled', 'metrics_management_interfaces',
            'prometheus_job', 'grafana_dashboard',
            'loki_labels', 'health_score', 'last_seen_at', 'external_id', 'metadata', 'site'
        ]

    def validate(self, data):
        # Validate network type fields
        validate_network_type_fields(data)
        return data

    def create(self, validated_data):
        request = self.context['request']
        validated_data['organization'] = getattr(request, "organization", None)
        
        # Extract metrics and SNMP data from the request
        metrics_data = {}
        snmp_data = {}
        
        # Get the original data before camelCase conversion
        original_data = self.context.get('request').data if hasattr(self.context.get('request'), 'data') else {}
        
        # Metrics fields
        if 'ilo' in original_data:
            metrics_data['ilo_enabled'] = original_data.get('ilo', False)
            metrics_data['ilo_username'] = original_data.get('iloUsername')
            metrics_data['ilo_password'] = original_data.get('iloPassword')
            metrics_data['ilo_ip'] = original_data.get('iloIp')
        if 'idrac' in original_data:
            metrics_data['idrac_enabled'] = original_data.get('idrac', False)
            metrics_data['idrac_port'] = original_data.get('idracPort')
        if 'nodeExporter' in original_data:
            metrics_data['node_exporter_enabled'] = original_data.get('nodeExporter', False)
            metrics_data['node_exporter_port'] = original_data.get('nodeExporterPort')
        if 'windowsExporter' in original_data:
            metrics_data['windows_exporter_enabled'] = original_data.get('windowsExporter', False)
            metrics_data['windows_exporter_port'] = original_data.get('windowsExporterPort')
        
        # SNMP fields
        if 'snmp' in original_data:
            snmp_data['snmp_enabled'] = original_data.get('snmp', False)
            snmp_data['snmp_version'] = original_data.get('snmpVersion')
            snmp_data['snmp_community_string'] = original_data.get('snmpCommunityString')
            snmp_data['snmp_username'] = original_data.get('snmpUsername')
            snmp_data['snmp_security_level'] = original_data.get('snmpSecurityLevel')
            snmp_data['snmp_auth_method'] = original_data.get('snmpAuthMethod')
            snmp_data['snmp_auth_password'] = original_data.get('snmpAuthPassword')
            snmp_data['snmp_privacy_method'] = original_data.get('snmpPrivacyMethod')
            snmp_data['snmp_privacy_password'] = original_data.get('snmpPrivacyPassword')
        
        # Validate metrics and SNMP data
        if metrics_data or snmp_data:
            validate_metrics_management_interfaces(original_data)
        
        # Create the configuration item
        ci = super().create(validated_data)
        
        # Create metrics management record if data exists
        if metrics_data and any(metrics_data.values()):
            AssetMetricsManagement.objects.create(configuration_item=ci, **metrics_data)
        
        # Create SNMP configuration record if data exists
        if snmp_data and any(snmp_data.values()):
            AssetSNMPConfiguration.objects.create(configuration_item=ci, **snmp_data)
        
        return ci


class ConfigurationItemUpdateSerializer(CamelCaseInputMixin, serializers.ModelSerializer):
    class Meta:
        model = ConfigurationItem
        fields = [
            'name', 'type', 'status', 'category', 'subcategory', 'template',
            'network_type', 'switch_type', 'firewall_type', 'router_type', 'description',
            'serial_number', 'asset_tag', 'manufacturer', 'model', 'version',
            'location', 'rack_position', 'data_center', 'ip_address', 'physical_ip_address',
            'mac_address', 'hostname', 'fqdn', 'cpu', 'memory', 'storage', 'os', 'os_version',
            'service_name', 'management_ip_address', 'environment',
            'owner', 'support_group', 'vendor', 'purchase_date', 'warranty_expiry',
            'end_of_life', 'end_of_support', 'purchase_cost', 'monthly_cost',
            'cost_center', 'monitoring_enabled', 'metrics_management_interfaces',
            'prometheus_job', 'grafana_dashboard',
            'loki_labels', 'health_score', 'last_seen_at', 'external_id', 'metadata', 'site'
        ]


class AssetSiteSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source='organization',
        queryset=Organization.objects.all(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = AssetSite
        fields = [
            'id', 'organization', 'organization_id', 'name', 'slug', 'environment', 'location', 'country', 'state',
            'latitude', 'longitude', 'entity_host', 'entity_port', 'entity_secure',
            'websocket_host', 'websocket_port', 'websocket_secure', 'redis_url',
            'prometheus_url', 'grafana_url', 'redmine_url', 'incident_url',
            'status', 'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}


class AssetCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCatalog
        fields = ['id', 'category', 'name', 'parent', 'is_active', 'metadata', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssetManagementEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetManagementEndpoint
        fields = [
            'id', 'configuration_item', 'protocol', 'management_ip', 'ilo_ip',
            'port', 'username', 'secret_ref', 'threshold', 'is_active',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'configuration_item': {'required': False}}


class AssetRelationshipSerializer(serializers.ModelSerializer):
    source_ci_detail = ConfigurationItemSerializer(source='source_ci', read_only=True)
    target_ci_detail = ConfigurationItemSerializer(source='target_ci', read_only=True)

    class Meta:
        model = AssetRelationship
        fields = [
            'id', 'source_ci', 'target_ci', 'relationship_type', 'label',
            'source_port', 'target_port', 'metadata', 'source_ci_detail',
            'target_ci_detail', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
        extra_kwargs = {'source_ci': {'required': False}}


class AssetPortConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPortConnection
        fields = [
            'id', 'source_ci', 'target_ci', 'source_modal', 'source_ip',
            'source_port', 'source_name', 'destination_modal', 'destination_ip',
            'destination_port', 'destination_name', 'status', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssetDiscoveryResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDiscoveryResult
        fields = [
            'id', 'site', 'scan_range_start', 'scan_range_end', 'ip_address',
            'hostname', 'asset_type', 'status', 'discovered_data', 'accepted_ci',
            'discovered_at', 'updated_at',
        ]
        read_only_fields = ['id', 'discovered_at', 'updated_at']


class AssetOnboardingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetOnboardingRecord
        fields = [
            'id', 'configuration_item', 'discovery_result', 'site', 'select_host',
            'ip_address', 'sub_ip_address', 'server_type', 'contact_email',
            'service_name', 'path_host', 'hostname', 'physical_ip_address',
            'main_ip_address', 'raw_json', 'raw_text', 'status', 'error_message',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'configuration_item', 'status', 'error_message', 'created_by', 'created_at', 'updated_at']


class AssetMetricsManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetMetricsManagement
        fields = [
            'id', 'configuration_item',
            'ilo_enabled', 'ilo_username', 'ilo_password', 'ilo_ip',
            'idrac_enabled', 'idrac_port',
            'node_exporter_enabled', 'node_exporter_port',
            'windows_exporter_enabled', 'windows_exporter_port',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssetSNMPConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetSNMPConfiguration
        fields = [
            'id', 'configuration_item',
            'snmp_enabled', 'snmp_version', 'snmp_community_string',
            'snmp_username', 'snmp_security_level', 'snmp_auth_method',
            'snmp_auth_password', 'snmp_privacy_method', 'snmp_privacy_password',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
