from django_filters import rest_framework as filters
from .models import Incident

class IncidentFilter(filters.FilterSet):
    assigned_to_me = filters.BooleanFilter(method='filter_assigned_to_me')
    search = filters.CharFilter(method='filter_search')
    date_from = filters.DateTimeFilter(field_name="created_at", lookup_expr='gte')
    date_to = filters.DateTimeFilter(field_name="created_at", lookup_expr='lte')

    class Meta:
        model = Incident
        fields = ['state', 'priority', 'category', 'subcategory', 'assigned_to', 'assignment_group', 'source', 'sla_breached']

    def filter_assigned_to_me(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            return queryset.filter(assigned_to=self.request.user)
        return queryset

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(number__icontains=value) | 
            Q(short_description__icontains=value) |
            Q(description__icontains=value)
        )
