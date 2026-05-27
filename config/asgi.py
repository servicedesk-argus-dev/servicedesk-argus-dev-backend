import os
import logging
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)
django_application = get_asgi_application()

try:
    from apps.notifications.realtime import create_socketio_application

    application = create_socketio_application(django_application)
except Exception:
    logger.exception("Socket.IO ASGI application setup failed; serving Django ASGI only")
    application = django_application
