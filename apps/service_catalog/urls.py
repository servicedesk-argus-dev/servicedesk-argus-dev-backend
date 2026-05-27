from django.urls import path

from .views import (
    CatalogTaskDetailView,
    CatalogCategoryListCreateView,
    CatalogItemDetailView,
    CatalogItemListCreateView,
    MyServiceRequestListView,
    ServiceRequestApproveView,
    ServiceRequestCloseView,
    ServiceRequestDetailView,
    ServiceRequestListCreateView,
    ServiceRequestReopenView,
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
    path("service-requests/<uuid:pk>/close/", ServiceRequestCloseView.as_view()),
    path("service-requests/<uuid:pk>/reopen/", ServiceRequestReopenView.as_view()),
    path("catalog-tasks/<uuid:pk>/", CatalogTaskDetailView.as_view()),
]
