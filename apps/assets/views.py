import ipaddress
import uuid

from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.mixins import OrgQuerysetMixin
from apps.common.responses import failure, success
from apps.organizations.models import Organization
from .bootstrap import bootstrap_inventory_if_demo
from .models import (
    AssetCatalog,
    AssetDiscoveryResult,
    AssetManagementEndpoint,
    AssetOnboardingRecord,
    AssetPortConnection,
    AssetRelationship,
    AssetSite,
    ConfigurationItem,
)
from .services import AssetDiscoveryService, AssetLiveStatusService, PrometheusConfigService
from .serializers import (
    AssetCatalogSerializer,
    AssetDiscoveryResultSerializer,
    AssetManagementEndpointSerializer,
    AssetOnboardingRecordSerializer,
    AssetPortConnectionSerializer,
    AssetRelationshipSerializer,
    AssetSiteSerializer,
    ConfigurationItemCreateSerializer,
    ConfigurationItemSerializer,
    ConfigurationItemUpdateSerializer,
)


from rest_framework.exceptions import PermissionDenied
from apps.common.permissions import DenyViewerMutations, IsAdminOrManager, is_service_desk_staff


class AssetOrgMixin:
    permission_classes = [IsAuthenticated, DenyViewerMutations]

    def org_id(self, required=True):
        organization = getattr(self.request, "organization", None)
        if organization is None:
            if not required and is_service_desk_staff(self.request.user):
                return None
            raise PermissionDenied("Organization access denied")
        return str(organization.id)

    def organization(self, required=True):
        organization = getattr(self.request, "organization", None)
        if organization is None:
            if not required and is_service_desk_staff(self.request.user):
                return None
            raise PermissionDenied("Organization access denied")
        return organization


class ConfigurationItemListCreateView(AssetOrgMixin, OrgQuerysetMixin, generics.ListCreateAPIView):
    queryset = ConfigurationItem.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type', 'status', 'category', 'site', 'environment']

    def get_queryset(self):
        org_id = self.org_id(required=False)
        if org_id:
            self._ensure_default_seed(org_id)
        queryset = super().get_queryset().select_related('owner', 'support_group', 'site', 'organization')

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(hostname__icontains=search)
                | Q(ip_address__icontains=search)
                | Q(management_ip_address__icontains=search)
                | Q(serial_number__icontains=search)
                | Q(asset_tag__icontains=search)
                | Q(category__icontains=search)
                | Q(subcategory__icontains=search)
                | Q(service_name__icontains=search)
                | Q(owner__first_name__icontains=search)
                | Q(owner__last_name__icontains=search)
                | Q(owner__email__icontains=search)
                | Q(support_group__name__icontains=search)
                | Q(site__name__icontains=search)
            )

        return queryset

    def _ensure_default_seed(self, org_id):
        org = Organization.objects.filter(id=org_id).first()
        if org is None:
            return
        bootstrap_inventory_if_demo(org)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ConfigurationItemCreateSerializer
        return ConfigurationItemSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        ci = serializer.save()
        return success(ConfigurationItemSerializer(ci).data, "configuration item created", 201)


class ConfigurationItemDetailView(AssetOrgMixin, OrgQuerysetMixin, generics.RetrieveUpdateAPIView):
    queryset = ConfigurationItem.objects.all()

    def get_queryset(self):
        return super().get_queryset().select_related(
            'owner', 'support_group', 'site', 'organization'
        )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ConfigurationItemUpdateSerializer
        return ConfigurationItemSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        ci = serializer.save()
        return success(ConfigurationItemSerializer(ci).data, "configuration item updated")


class ConfigurationItemStatsView(AssetOrgMixin, generics.GenericAPIView):
    def get(self, request):
        org_id = self.org_id(required=False)
        queryset = ConfigurationItem.objects.all()
        relationship_queryset = AssetRelationship.objects.all()
        discovery_queryset = AssetDiscoveryResult.objects.all()
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
            relationship_queryset = relationship_queryset.filter(organization_id=org_id)
            discovery_queryset = discovery_queryset.filter(organization_id=org_id)

        stats = {
            'total': queryset.count(),
            'by_type': dict(queryset.values_list('type').annotate(count=models.Count('id'))),
            'by_status': dict(queryset.values_list('status').annotate(count=models.Count('id'))),
            'by_site': dict(queryset.exclude(site__isnull=True).values_list('site__name').annotate(count=models.Count('id'))),
            'monitoring_enabled': queryset.filter(monitoring_enabled=True).count(),
            'relationship_count': relationship_queryset.count(),
            'discovery_new': discovery_queryset.filter(status=AssetDiscoveryResult.Status.NEW).count(),
        }

        return success(stats)


class AssetTypesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success(
            {
                "types": [{"value": value, "label": label} for value, label in ConfigurationItem.Type.choices],
                "statuses": [{"value": value, "label": label} for value, label in ConfigurationItem.Status.choices],
                "catalog_categories": [{"value": value, "label": label} for value, label in AssetCatalog.Category.choices],
                "relationship_types": [{"value": value, "label": label} for value, label in AssetRelationship.RelationshipType.choices],
            }
        )


class AssetSiteListCreateView(AssetOrgMixin, OrgQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = AssetSiteSerializer
    queryset = AssetSite.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['environment', 'status']

    def perform_create(self, serializer):
        name = serializer.validated_data.get("name")
        slug = serializer.validated_data.get("slug") or slugify(name)
        organization = serializer.validated_data.get("organization")
        if not is_service_desk_staff(self.request.user):
            organization = self.request.organization
        if organization is None:
            raise serializers.ValidationError({"organization_id": "Site must be linked to a client organization."})
        serializer.save(organization=organization, slug=slug)


class AssetSiteDetailView(AssetOrgMixin, OrgQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssetSiteSerializer
    queryset = AssetSite.objects.all()

    def perform_update(self, serializer):
        organization = serializer.validated_data.get("organization")
        if organization is not None and not is_service_desk_staff(self.request.user):
            raise PermissionDenied("Only service desk admins can move sites between clients.")
        serializer.save()


class AssetCatalogListCreateView(AssetOrgMixin, OrgQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = AssetCatalogSerializer
    queryset = AssetCatalog.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active']

    def get_queryset(self):
        queryset = super().get_queryset()
        return AssetCatalog.objects.filter(Q(pk__in=queryset.values("pk")) | Q(organization__isnull=True))

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class AssetManagementEndpointListCreateView(AssetOrgMixin, OrgQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = AssetManagementEndpointSerializer
    queryset = AssetManagementEndpoint.objects.all()
    organization_lookup = "configuration_item__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['protocol', 'is_active']

    def get_configuration_item(self):
        return ConfigurationItem.objects.get(id=self.kwargs["pk"], organization=self.request.organization)

    def get_queryset(self):
        return super().get_queryset().filter(configuration_item=self.get_configuration_item())

    def perform_create(self, serializer):
        serializer.save(configuration_item=self.get_configuration_item())


class AssetRelationshipListCreateView(AssetOrgMixin, OrgQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = AssetRelationshipSerializer
    queryset = AssetRelationship.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['relationship_type']

    def get_configuration_item(self):
        return ConfigurationItem.objects.get(id=self.kwargs["pk"], organization=self.request.organization)

    def get_queryset(self):
        ci = self.get_configuration_item()
        return super().get_queryset().filter(Q(source_ci=ci) | Q(target_ci=ci)).select_related(
            'source_ci', 'target_ci', 'created_by'
        )

    def perform_create(self, serializer):
        ci = self.get_configuration_item()
        source_ci = serializer.validated_data.get("source_ci") or ci
        target_ci = serializer.validated_data["target_ci"]
        org_id = self.org_id()
        if str(source_ci.organization_id) != org_id or str(target_ci.organization_id) != org_id:
            raise serializers.ValidationError("Related assets must belong to the current organization.")
        serializer.save(organization=self.request.organization, source_ci=source_ci, created_by=self.request.user)


def _asset_summary(asset):
    if asset is None:
        return None
    return {
        "id": str(asset.id),
        "name": asset.name,
        "ciNumber": asset.asset_tag or asset.external_id or str(asset.id)[:8],
        "type": asset.type,
        "status": asset.status,
        "hostname": asset.hostname,
        "ipAddress": str(asset.ip_address) if asset.ip_address else None,
    }


def _asset_metadata(asset):
    return dict(asset.metadata or {})


def _metadata_list(asset, key):
    metadata = _asset_metadata(asset)
    value = metadata.get(key)
    return value if isinstance(value, list) else []


def _save_metadata(asset, metadata):
    asset.metadata = metadata
    asset.save(update_fields=["metadata", "updated_at"])


def _now_iso():
    return timezone.now().isoformat()


class AssetCompatibilityMixin(AssetOrgMixin):
    def get_asset(self, pk):
        return ConfigurationItem.objects.filter(organization=self.request.organization).select_related(
            "owner", "support_group", "site", "organization"
        ).get(id=pk)


class AssetRelationshipCompatView(AssetCompatibilityMixin, APIView):
    def _serialize(self, relationship, current_asset):
        target = relationship.target_ci if relationship.source_ci_id == current_asset.id else relationship.source_ci
        source = relationship.source_ci if relationship.source_ci_id == current_asset.id else relationship.target_ci
        return {
            "id": str(relationship.id),
            "type": relationship.relationship_type,
            "relationshipType": relationship.relationship_type,
            "label": relationship.label,
            "sourceAssetId": str(source.id),
            "targetAssetId": str(target.id),
            "sourceAsset": _asset_summary(source),
            "targetAsset": _asset_summary(target),
            "sourcePort": relationship.source_port,
            "targetPort": relationship.target_port,
            "createdAt": relationship.created_at.isoformat() if relationship.created_at else None,
            "updatedAt": relationship.updated_at.isoformat() if relationship.updated_at else None,
        }

    def get(self, request, pk):
        asset = self.get_asset(pk)
        relationships = AssetRelationship.objects.filter(Q(source_ci=asset) | Q(target_ci=asset)).select_related(
            "source_ci", "target_ci"
        )
        return success([self._serialize(relationship, asset) for relationship in relationships])

    def post(self, request, pk):
        asset = self.get_asset(pk)
        target_id = request.data.get("targetAssetId") or request.data.get("target_ci") or request.data.get("targetCi")
        relationship_type = request.data.get("type") or request.data.get("relationshipType") or request.data.get("relationship_type")
        if not target_id or not relationship_type:
            return failure("targetAssetId and type are required", status_code=400)

        target = ConfigurationItem.objects.filter(id=target_id, organization=self.request.organization).first()
        if target is None:
            return failure("target asset not found", status_code=404)
        if target.id == asset.id:
            return failure("target asset must be different from source asset", status_code=400)

        relationship, _ = AssetRelationship.objects.get_or_create(
            organization=self.request.organization,
            source_ci=asset,
            target_ci=target,
            relationship_type=relationship_type,
            defaults={
                "label": request.data.get("label", ""),
                "source_port": request.data.get("sourcePort") or request.data.get("source_port"),
                "target_port": request.data.get("targetPort") or request.data.get("target_port"),
                "metadata": request.data.get("metadata") or {},
                "created_by": request.user,
            },
        )
        return success(self._serialize(relationship, asset), "relationship saved", 201)


class AssetRelationshipDeleteCompatView(AssetCompatibilityMixin, APIView):
    def delete(self, request, pk, relationship_id):
        asset = self.get_asset(pk)
        deleted, _ = AssetRelationship.objects.filter(
            Q(source_ci=asset) | Q(target_ci=asset),
            id=relationship_id,
            organization=self.request.organization,
        ).delete()
        if not deleted:
            return failure("relationship not found", status_code=404)
        return success({"deleted": True}, "relationship removed")


class AssetDependencyMapView(AssetCompatibilityMixin, APIView):
    def get(self, request, pk):
        asset = self.get_asset(pk)
        relationships = AssetRelationship.objects.filter(source_ci=asset).select_related("target_ci")
        children = [
            {
                **_asset_summary(relationship.target_ci),
                "relationshipType": relationship.relationship_type,
                "children": [],
            }
            for relationship in relationships
        ]
        return success({**_asset_summary(asset), "children": children})


class AssetFinancialsView(AssetCompatibilityMixin, APIView):
    def _default_financials(self, asset):
        metadata = _asset_metadata(asset)
        financials = metadata.get("financials")
        if isinstance(financials, dict) and financials:
            return financials
        if not any([asset.purchase_date, asset.purchase_cost, asset.vendor, asset.warranty_expiry]):
            return None
        return {
            "purchaseDate": asset.purchase_date.isoformat() if asset.purchase_date else None,
            "invoiceNumber": None,
            "quantity": 1,
            "unitPrice": float(asset.purchase_cost or 0),
            "totalPrice": float(asset.purchase_cost or 0),
            "currency": "INR",
            "purchaseOrderNumber": None,
            "vendorId": slugify(asset.vendor) if asset.vendor else "",
            "vendor": {"id": slugify(asset.vendor), "name": asset.vendor} if asset.vendor else None,
            "warrantyEndDate": asset.warranty_expiry.isoformat() if asset.warranty_expiry else None,
        }

    def get(self, request, pk):
        return success(self._default_financials(self.get_asset(pk)))

    def put(self, request, pk):
        asset = self.get_asset(pk)
        payload = dict(request.data)
        vendor_id = payload.get("vendorId")
        if vendor_id and not payload.get("vendor"):
            vendor_name = next((vendor["name"] for vendor in _vendor_rows(self.org_id()) if vendor["id"] == vendor_id), None)
            if vendor_name:
                payload["vendor"] = {"id": vendor_id, "name": vendor_name}
        metadata = _asset_metadata(asset)
        payload["updatedAt"] = _now_iso()
        metadata["financials"] = payload
        _save_metadata(asset, metadata)
        return success(payload, "financial data saved")


class AssetMetadataListView(AssetCompatibilityMixin, APIView):
    metadata_key = ""
    default_message = "item saved"

    def get(self, request, pk):
        asset = self.get_asset(pk)
        return success(_metadata_list(asset, self.metadata_key))

    def post(self, request, pk):
        asset = self.get_asset(pk)
        metadata = _asset_metadata(asset)
        rows = _metadata_list(asset, self.metadata_key)
        row = dict(request.data)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("createdAt", _now_iso())
        rows.append(row)
        metadata[self.metadata_key] = rows
        _save_metadata(asset, metadata)
        return success(row, self.default_message, 201)


class AssetAllocationsView(AssetMetadataListView):
    metadata_key = "allocations"
    default_message = "allocation saved"


class AssetAllocationReturnView(AssetCompatibilityMixin, APIView):
    def post(self, request, pk, allocation_id):
        asset = self.get_asset(pk)
        metadata = _asset_metadata(asset)
        rows = _metadata_list(asset, "allocations")
        for row in rows:
            if str(row.get("id")) == str(allocation_id):
                row["returnedAt"] = row.get("returnedAt") or _now_iso()
                metadata["allocations"] = rows
                _save_metadata(asset, metadata)
                return success(row, "asset returned")
        return failure("allocation not found", status_code=404)


class AssetDisposalView(AssetCompatibilityMixin, APIView):
    def get(self, request, pk):
        asset = self.get_asset(pk)
        disposal = _asset_metadata(asset).get("disposal")
        return success(disposal if isinstance(disposal, dict) else None)

    def post(self, request, pk):
        asset = self.get_asset(pk)
        metadata = _asset_metadata(asset)
        payload = dict(request.data)
        payload.setdefault("id", str(uuid.uuid4()))
        payload.setdefault("createdAt", _now_iso())
        metadata["disposal"] = payload
        _save_metadata(asset, metadata)
        return success(payload, "disposal recorded", 201)


class AssetMovementsView(AssetMetadataListView):
    metadata_key = "movements"
    default_message = "movement recorded"


class AssetConnectionsView(AssetCompatibilityMixin, APIView):
    def get(self, request, pk):
        asset = self.get_asset(pk)
        connections = AssetPortConnection.objects.filter(
            Q(source_ci=asset) | Q(target_ci=asset), organization=self.request.organization
        )
        return success(AssetPortConnectionSerializer(connections, many=True).data)

    def post(self, request, pk):
        asset = self.get_asset(pk)
        payload = dict(request.data)
        payload.setdefault("source_ci", str(asset.id))
        serializer = AssetPortConnectionSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        connection = serializer.save(organization=self.request.organization)
        return success(AssetPortConnectionSerializer(connection).data, "connection saved", 201)


class AssetIPAddressesView(AssetCompatibilityMixin, APIView):
    def get(self, request, pk):
        asset = self.get_asset(pk)
        rows = []
        if asset.ip_address:
            rows.append({"id": "primary", "address": str(asset.ip_address), "type": "primary", "label": "Primary IP"})
        if asset.management_ip_address and asset.management_ip_address != asset.ip_address:
            rows.append({"id": "management", "address": str(asset.management_ip_address), "type": "management", "label": "Management IP"})
        return success(rows)


def _vendor_rows(org_id):
    values = set()
    queryset = ConfigurationItem.objects.filter(organization_id=org_id)
    for value in queryset.exclude(vendor__isnull=True).exclude(vendor="").values_list("vendor", flat=True):
        values.add(value)
    for value in queryset.exclude(manufacturer__isnull=True).exclude(manufacturer="").values_list("manufacturer", flat=True):
        values.add(value)
    return [{"id": slugify(value), "name": value, "isActive": True} for value in sorted(values)]


class AssetVendorsView(AssetOrgMixin, APIView):
    def get(self, request):
        return success(_vendor_rows(self.org_id()))

    def post(self, request):
        name = request.data.get("name")
        if not name:
            return failure("name is required", status_code=400)
        return success({"id": slugify(name), "name": name, "isActive": True}, "vendor saved", 201)


class AssetVendorDetailView(AssetOrgMixin, APIView):
    def patch(self, request, vendor_id):
        payload = {"id": vendor_id, "name": request.data.get("name") or vendor_id, "isActive": request.data.get("isActive", True)}
        return success(payload, "vendor updated")

    def delete(self, request, vendor_id):
        return success({"deleted": True}, "vendor removed")


class AssetTopologyView(AssetOrgMixin, APIView):
    def get(self, request):
        org_id = self.org_id()
        assets = ConfigurationItem.objects.filter(organization=request.organization).select_related('site')
        relationships = AssetRelationship.objects.filter(organization=request.organization)

        nodes = [
            {
                "id": str(asset.id),
                "name": asset.name,
                "type": asset.type,
                "status": asset.status,
                "site": asset.site.name if asset.site else None,
                "ip_address": str(asset.ip_address) if asset.ip_address else None,
            }
            for asset in assets
        ]
        edges = [
            {
                "id": str(rel.id),
                "source": str(rel.source_ci_id),
                "target": str(rel.target_ci_id),
                "type": rel.relationship_type,
                "label": rel.label,
                "source_port": rel.source_port,
                "target_port": rel.target_port,
            }
            for rel in relationships
        ]
        return success({"nodes": nodes, "edges": edges})


class AssetLiveMetricsView(AssetOrgMixin, APIView):
    def get_asset(self, pk):
        return ConfigurationItem.objects.filter(organization=self.request.organization).prefetch_related(
            "management_endpoints"
        ).select_related("site").get(id=pk)

    def get(self, request, pk):
        asset = self.get_asset(pk)
        refresh = request.query_params.get("refresh") == "true"
        payload = AssetLiveStatusService.refresh(asset) if refresh else AssetLiveStatusService.get_or_refresh(asset)
        return success(payload)

    def post(self, request, pk):
        asset = self.get_asset(pk)
        return success(AssetLiveStatusService.refresh(asset), "asset live status refreshed")


class AssetMetricsHistoryView(AssetOrgMixin, APIView):
    def get(self, request, pk):
        asset = ConfigurationItem.objects.filter(organization=request.organization).prefetch_related(
            "management_endpoints"
        ).select_related("site").get(id=pk)
        duration = request.query_params.get("duration", "6h")
        return success(AssetLiveStatusService.history(asset, duration=duration))


class AssetLiveStatusSyncView(AssetOrgMixin, APIView):
    def post(self, request):
        queryset = ConfigurationItem.objects.filter(organization=request.organization, monitoring_enabled=True)
        asset_ids = request.data.get("asset_ids")
        if asset_ids:
            queryset = queryset.filter(id__in=asset_ids)

        refreshed = []
        for asset in queryset.prefetch_related("management_endpoints").select_related("site"):
            refreshed.append(AssetLiveStatusService.refresh(asset))
        return success({"refreshed": len(refreshed), "assets": refreshed}, "asset live status synced")


class AssetPrometheusConfigView(AssetOrgMixin, APIView):
    def get(self, request):
        content = PrometheusConfigService.generate(self.org_id())
        if request.query_params.get("format") == "yaml":
            return HttpResponse(content, content_type="text/yaml")
        return success({"content": content})

    def post(self, request):
        path, content = PrometheusConfigService.write(self.org_id())
        return success({"path": str(path), "content": content}, "prometheus config generated")


class AssetPortConnectionListCreateView(AssetOrgMixin, OrgQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = AssetPortConnectionSerializer
    queryset = AssetPortConnection.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'source_ci', 'target_ci']

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(source_name__icontains=search)
                | Q(destination_name__icontains=search)
                | Q(source_ip__icontains=search)
                | Q(destination_ip__icontains=search)
                | Q(source_port__icontains=search)
                | Q(destination_port__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class AssetPortConnectionImportView(AssetOrgMixin, APIView):
    def post(self, request):
        rows = request.data.get("rows", [])
        if not isinstance(rows, list) or not rows:
            return failure("rows must be a non-empty list", status_code=400)

        created = []
        for row in rows:
            serializer = AssetPortConnectionSerializer(data=row)
            serializer.is_valid(raise_exception=True)
            created.append(serializer.save(organization=self.request.organization))

        return success(AssetPortConnectionSerializer(created, many=True).data, "port connections imported", 201)


class AssetPortConnectionExportView(AssetOrgMixin, APIView):
    def get(self, request):
        rows = AssetPortConnection.objects.filter(organization=request.organization)
        return success(AssetPortConnectionSerializer(rows, many=True).data)


class AssetDiscoveryResultListView(AssetOrgMixin, OrgQuerysetMixin, generics.ListAPIView):
    serializer_class = AssetDiscoveryResultSerializer
    queryset = AssetDiscoveryResult.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'asset_type', 'site']


class AssetDiscoveryScanView(AssetOrgMixin, APIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def post(self, request):
        start = request.data.get("from_ip") or request.data.get("scan_range_start")
        end = request.data.get("to_ip") or request.data.get("scan_range_end") or start
        site_id = request.data.get("site") or request.data.get("site_id")
        asset_type = request.data.get("asset_type") or ConfigurationItem.Type.SERVER

        if not start:
            return failure("from_ip is required", status_code=400)

        try:
            start_ip = ipaddress.ip_address(start)
            end_ip = ipaddress.ip_address(end)
        except ValueError:
            return failure("Invalid IP range", status_code=400)

        if int(end_ip) < int(start_ip):
            return failure("to_ip must be greater than or equal to from_ip", status_code=400)

        size = int(end_ip) - int(start_ip) + 1
        if size > 64:
            return failure("Discovery scan is limited to 64 IPs per request in this API path", status_code=400)

        site = None
        if site_id:
            site = AssetSite.objects.filter(id=site_id, organization=request.organization).first()
            if site is None:
                return failure("site not found", status_code=404)

        results = []
        for offset in range(size):
            current = ipaddress.ip_address(int(start_ip) + offset)
            probed = AssetDiscoveryService.probe_host(str(current), asset_type=asset_type)
            result = AssetDiscoveryResult.objects.create(
                organization=request.organization,
                site=site,
                scan_range_start=str(start_ip),
                scan_range_end=str(end_ip),
                ip_address=str(current),
                hostname=probed.get("hostname"),
                asset_type=asset_type,
                discovered_data=probed,
            )
            results.append(result)

        return success(AssetDiscoveryResultSerializer(results, many=True).data, "discovery scan recorded", 201)


class AssetOnboardingListView(AssetOrgMixin, OrgQuerysetMixin, generics.ListAPIView):
    serializer_class = AssetOnboardingRecordSerializer
    queryset = AssetOnboardingRecord.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'site']


class AssetOnboardView(AssetOrgMixin, APIView):
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def post(self, request):
        discovery_result = None
        discovery_id = request.data.get("discovery_result") or request.data.get("discoveryResultId")
        if discovery_id:
            discovery_result = AssetDiscoveryResult.objects.filter(id=discovery_id, organization=request.organization).first()
            if discovery_result is None:
                return failure("discovery_result not found", status_code=404)

        site_id = request.data.get("site") or request.data.get("siteId")
        if not site_id and discovery_result and discovery_result.site_id:
            site_id = str(discovery_result.site_id)
        site = AssetSite.objects.filter(id=site_id, organization=request.organization).first() if site_id else None

        name = request.data.get("name") or request.data.get("hostname") or (discovery_result.hostname if discovery_result else None)
        ip_address = request.data.get("ip_address") or request.data.get("ipAddress") or (str(discovery_result.ip_address) if discovery_result else None)
        asset_type = request.data.get("type") or request.data.get("asset_type") or (discovery_result.asset_type if discovery_result else ConfigurationItem.Type.SERVER)
        if not name:
            return failure("name or hostname is required", status_code=400)

        ci = ConfigurationItem.objects.create(
            organization=request.organization,
            site=site,
            name=name,
            type=asset_type,
            status=ConfigurationItem.Status.LIVE,
            hostname=request.data.get("hostname") or name,
            ip_address=ip_address,
            category=request.data.get("category"),
            subcategory=request.data.get("subcategory"),
            service_name=request.data.get("service_name") or request.data.get("serviceName"),
            environment=site.environment if site else request.data.get("environment"),
            metadata=request.data.get("metadata") or {},
        )

        record = AssetOnboardingRecord.objects.create(
            organization=request.organization,
            configuration_item=ci,
            discovery_result=discovery_result,
            site=site,
            select_host=request.data.get("select_host") or request.data.get("selectHost"),
            ip_address=ip_address,
            sub_ip_address=request.data.get("sub_ip_address") or request.data.get("subIpAddress"),
            server_type=request.data.get("server_type") or request.data.get("serverType"),
            contact_email=request.data.get("contact_email") or request.data.get("contactEmail"),
            service_name=ci.service_name,
            path_host=request.data.get("path_host") or request.data.get("pathHost"),
            hostname=ci.hostname,
            physical_ip_address=request.data.get("physical_ip_address") or request.data.get("physicalIpAddress"),
            main_ip_address=request.data.get("main_ip_address") or request.data.get("mainIpAddress"),
            raw_json=request.data.get("raw_json") or request.data.get("rawJson") or {},
            raw_text=request.data.get("raw_text") or request.data.get("rawText"),
            status=AssetOnboardingRecord.Status.ONBOARDED,
            created_by=request.user,
        )

        if discovery_result:
            discovery_result.status = AssetDiscoveryResult.Status.ACCEPTED
            discovery_result.accepted_ci = ci
            discovery_result.save(update_fields=["status", "accepted_ci", "updated_at"])

        return success(
            {
                "asset": ConfigurationItemSerializer(ci).data,
                "onboarding": AssetOnboardingRecordSerializer(record).data,
            },
            "asset onboarded",
            status.HTTP_201_CREATED,
        )
