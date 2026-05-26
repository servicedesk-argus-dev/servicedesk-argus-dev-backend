from django.apps import AppConfig


class ChangesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.changes'

    def ready(self):
        from . import signals  # noqa: F401
