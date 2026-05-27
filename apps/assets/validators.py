from rest_framework import serializers


def validate_metrics_management_interfaces(data):
    """
    Validate metrics and management interfaces fields based on asset type.
    
    This validator ensures that when a management interface is enabled,
    its required configuration fields are also provided.
    """
    ilo = data.get('ilo', False)
    idrac = data.get('idrac', False)
    node_exporter = data.get('nodeExporter', False)
    windows_exporter = data.get('windowsExporter', False)
    snmp = data.get('snmp', False)
    
    errors = {}
    
    # ILO validation
    if ilo:
        ilo_username = data.get('iloUsername')
        ilo_password = data.get('iloPassword')
        ilo_ip = data.get('iloIp')
        
        if not ilo_username:
            errors['iloUsername'] = 'ILO username is required when ILO is enabled'
        if not ilo_password:
            errors['iloPassword'] = 'ILO password is required when ILO is enabled'
        if not ilo_ip:
            errors['iloIp'] = 'ILO IP is required when ILO is enabled'
    
    # IDRAC validation
    if idrac:
        idrac_port = data.get('idracPort')
        if not idrac_port:
            errors['idracPort'] = 'IDRAC port is required when IDRAC is enabled'
    
    # Node Exporter validation
    if node_exporter:
        node_exporter_port = data.get('nodeExporterPort')
        if not node_exporter_port:
            errors['nodeExporterPort'] = 'Node Exporter port is required when Node Exporter is enabled'
    
    # Windows Exporter validation
    if windows_exporter:
        windows_exporter_port = data.get('windowsExporterPort')
        if not windows_exporter_port:
            errors['windowsExporterPort'] = 'Windows Exporter port is required when Windows Exporter is enabled'
    
    # SNMP validation
    if snmp:
        snmp_version = data.get('snmpVersion')
        if not snmp_version:
            errors['snmpVersion'] = 'SNMP version is required when SNMP is enabled'
        
        if snmp_version == 'v2c':
            snmp_community_string = data.get('snmpCommunityString')
            if not snmp_community_string:
                errors['snmpCommunityString'] = 'SNMP community string is required for SNMP v2c'
        
        elif snmp_version == 'v3':
            snmp_username = data.get('snmpUsername')
            snmp_security_level = data.get('snmpSecurityLevel')
            snmp_auth_method = data.get('snmpAuthMethod')
            snmp_auth_password = data.get('snmpAuthPassword')
            snmp_privacy_method = data.get('snmpPrivacyMethod')
            snmp_privacy_password = data.get('snmpPrivacyPassword')
            
            if not snmp_username:
                errors['snmpUsername'] = 'SNMP username is required for SNMP v3'
            if not snmp_security_level:
                errors['snmpSecurityLevel'] = 'SNMP security level is required for SNMP v3'
            if not snmp_auth_method:
                errors['snmpAuthMethod'] = 'SNMP auth method is required for SNMP v3'
            if not snmp_auth_password:
                errors['snmpAuthPassword'] = 'SNMP auth password is required for SNMP v3'
            if not snmp_privacy_method:
                errors['snmpPrivacyMethod'] = 'SNMP privacy method is required for SNMP v3'
            if not snmp_privacy_password:
                errors['snmpPrivacyPassword'] = 'SNMP privacy password is required for SNMP v3'
    
    if errors:
        raise serializers.ValidationError(errors)
    
    return data


def validate_network_type_fields(data):
    """
    Validate network type and subtype fields for network assets.
    
    This validator ensures that when a network type is selected,
    the appropriate subtype field is also provided.
    """
    asset_type = data.get('type')
    network_type = data.get('networkType')
    
    if asset_type == 'NETWORK':
        if not network_type:
            raise serializers.ValidationError({
                'networkType': 'Network type is required for network assets'
            })
        
        errors = {}
        
        if network_type == 'switch':
            switch_type = data.get('switchType')
            if not switch_type:
                errors['switchType'] = 'Switch type is required when network type is switch'
        
        elif network_type == 'firewall':
            firewall_type = data.get('firewallType')
            if not firewall_type:
                errors['firewallType'] = 'Firewall type is required when network type is firewall'
        
        elif network_type == 'router':
            router_type = data.get('routerType')
            if not router_type:
                errors['routerType'] = 'Router type is required when network type is router'
        
        if errors:
            raise serializers.ValidationError(errors)
    
    return data
