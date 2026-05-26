from django.apps import AppConfig


class ServiceCatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.service_catalog"

    def ready(self):
        from . import signals  # noqa: F401

