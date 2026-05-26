from rest_framework import viewsets, exceptions

class TenantAwareViewSetMixin:
    """
    Mixin to automatically filter querysets by the current organization (request.organization).
    Ensures Org A cannot see Org B's data.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        organization = getattr(self.request, 'organization', None)
        
        if not organization:
            # If for some reason the middleware didn't set the organization, 
            # and it's not an exempt path, we should deny access.
            raise exceptions.PermissionDenied("Organization context missing.")
            
        return queryset.filter(organization=organization)

    def perform_create(self, serializer):
        # Automatically assign the organization to the new record
        serializer.save(organization=self.request.organization)

class TenantAwareModelViewSet(TenantAwareViewSetMixin, viewsets.ModelViewSet):
    """
    A ModelViewSet that is tenant-aware.
    """
    pass
