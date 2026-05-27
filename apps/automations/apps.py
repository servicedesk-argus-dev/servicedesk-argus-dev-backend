from django.apps import AppConfig

class AutomationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automations'

    def ready(self):
        import apps.automations.signals
