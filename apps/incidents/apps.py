from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.incidents"

    def ready(self):
        import apps.incidents.signals

