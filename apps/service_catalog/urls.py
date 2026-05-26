from django.urls import path

from .views import (
    CatalogCategoryListCreateView,
    CatalogItemDetailView,
    CatalogItemListCreateView,
    MyServiceRequestListView,
    ServiceRequestApproveView,
    ServiceRequestDetailView,
    ServiceRequestListCreateView,
    ServiceRequestRejectView,
)

urlpatterns = [
    path("catalog/categories/", CatalogCategoryListCreateView.as_view()),
    path("catalog/items/", CatalogItemListCreateView.as_view()),
    path("catalog/items/<uuid:pk>/", CatalogItemDetailView.as_view()),
    path("service-requests/", ServiceRequestListCreateView.as_view()),
    path("service-requests/my/", MyServiceRequestListView.as_view()),
    path("service-requests/<uuid:pk>/", ServiceRequestDetailView.as_view()),
    path("service-requests/<uuid:pk>/approve/", ServiceRequestApproveView.as_view()),
    path("service-requests/<uuid:pk>/reject/", ServiceRequestRejectView.as_view()),
]
