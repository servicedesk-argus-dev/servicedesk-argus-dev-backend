import os
import sys
import warnings
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable is required")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"

# HS256: PyJWT recommends >= 32 bytes. Use JWT_SIGNING_KEY in production if SECRET_KEY is short.
JWT_SIGNING_KEY = (os.getenv("JWT_SIGNING_KEY", "") or SECRET_KEY).strip()
_jwt_key_len = len(JWT_SIGNING_KEY.encode("utf-8"))
if _jwt_key_len < 32:
    if DEBUG:
        warnings.warn(
            "JWT signing key is under 32 bytes (HS256). Set JWT_SIGNING_KEY or a longer DJANGO_SECRET_KEY to silence this.",
            stacklevel=1,
        )
    else:
        raise ImproperlyConfigured(
            "JWT_SIGNING_KEY (or DJANGO_SECRET_KEY) must be at least 32 bytes for HS256 when DEBUG is False."
        )

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CORS_ALLOWED_ORIGINS = [h.strip() for h in os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [h.strip() for h in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if h.strip()]

_trusted_proxy_raw = os.getenv("TRUSTED_PROXY_IPS", "")
TRUSTED_PROXY_IPS = tuple(x.strip() for x in _trusted_proxy_raw.split(",") if x.strip())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.organizations",
    "apps.accounts",
    "apps.incidents.apps.IncidentsConfig",
    "apps.changes.apps.ChangesConfig",
    "apps.problems.apps.ProblemsConfig",
    "apps.sla",
    "apps.alerts.apps.AlertsConfig",
    "apps.teams",
    "apps.dashboard",
    "apps.integrations",
    "apps.notifications",
    "apps.reports",
    "apps.search",
    "apps.assets.apps.AssetsConfig",
    "apps.apm",
    "apps.eod",
    "apps.illbandwidth",
    "apps.oms",
    "apps.webhooks",
    "apps.status",
    "apps.domain",
    "apps.workflows",
    "apps.automations",
    "apps.approvals",
    "apps.assignments",
    "apps.service_catalog.apps.ServiceCatalogConfig",
    "apps.learning.apps.LearningConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.OrganizationContextMiddleware",
    "apps.common.audit_middleware.AuditLogMiddleware",
    "apps.common.rate_limit_middleware.RateLimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Email Settings
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Argus Service Desk <noreply@argus.io>")

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.postgresql")
IS_RUNSERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"
DEFAULT_CONN_MAX_AGE = "0" if (DEBUG or IS_RUNSERVER) else "60"
DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": os.getenv("DB_NAME", "argus_servicedesk"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", DEFAULT_CONN_MAX_AGE)),
        "CONN_HEALTH_CHECKS": True,
        "ATOMIC_REQUESTS": True,
    }
}

if not DEBUG and not os.getenv("DB_PASSWORD", "").strip():
    raise ImproperlyConfigured("DB_PASSWORD is required when DEBUG is False.")

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "FORMAT_SUFFIX_KWARG": None,
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": JWT_SIGNING_KEY,
}

KEYCLOAK_ENABLED = os.getenv("KEYCLOAK_ENABLED", "true").lower() == "true"
KEYCLOAK_ISSUER = os.getenv(
    "KEYCLOAK_ISSUER",
    "http://localhost:8082/realms/ArgusService%20Desk",
).rstrip("/")
KEYCLOAK_JWKS_URL = os.getenv(
    "KEYCLOAK_JWKS_URL",
    f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs",
)
KEYCLOAK_ALLOWED_CLIENTS = tuple(
    client.strip()
    for client in os.getenv("KEYCLOAK_ALLOWED_CLIENTS", "argus-frontend,Argus-Frontend").split(",")
    if client.strip()
)
KEYCLOAK_RBAC_CLIENTS = tuple(
    client.strip()
    for client in os.getenv("KEYCLOAK_RBAC_CLIENTS", "Argus-Frontend,Argus-Backend").split(",")
    if client.strip()
)
KEYCLOAK_AUTO_CREATE_USERS = os.getenv("KEYCLOAK_AUTO_CREATE_USERS", "true").lower() == "true"
KEYCLOAK_DEFAULT_CLIENT_ORG = os.getenv("KEYCLOAK_DEFAULT_CLIENT_ORG", "").strip()
KEYCLOAK_SYNC_LOCAL_ROLES = os.getenv("KEYCLOAK_SYNC_LOCAL_ROLES", "true").lower() == "true"
KEYCLOAK_PASSWORD_LOGIN_ENABLED = os.getenv("KEYCLOAK_PASSWORD_LOGIN_ENABLED", "false").lower() == "true"
KEYCLOAK_PASSWORD_GRANT_CLIENT_ID = os.getenv("KEYCLOAK_PASSWORD_GRANT_CLIENT_ID", "").strip()
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "").strip()
KEYCLOAK_TOKEN_URL = os.getenv("KEYCLOAK_TOKEN_URL", "").strip()
KEYCLOAK_TOKEN_TIMEOUT = int(os.getenv("KEYCLOAK_TOKEN_TIMEOUT", "10"))

SPECTACULAR_SETTINGS = {
    "TITLE": "Argus Service Desk Python API",
    "DESCRIPTION": "Production-grade Python backend for Argus Service Desk.",
    "VERSION": "1.0.0",
    "TAGS": [
        {"name": "incidents", "description": "Incident lifecycle and SLA"},
        {"name": "problems", "description": "Problem management"},
        {"name": "changes", "description": "Change management and approvals"},
        {"name": "sla", "description": "SLA definitions and calendars"},
        {"name": "status", "description": "Health and operational probes"},
    ],
}

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", REDIS_URL)
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
PROMETHEUS_FILE_SD_PATH = os.getenv("PROMETHEUS_FILE_SD_PATH", "/etc/prometheus/file_sd")
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL")
if not DEBUG and not ALERTMANAGER_URL:
    raise ImproperlyConfigured("ALERTMANAGER_URL environment variable is required when DEBUG is False")

# Inbound machine-to-machine webhook auth. LinkedEye sends this as:
# Authorization: Bearer <ARGUS_API_TOKEN>
ARGUS_WEBHOOK_API_TOKEN = os.getenv("ARGUS_WEBHOOK_API_TOKEN", os.getenv("ARGUS_API_TOKEN", "")).strip()
ARGUS_WEBHOOK_SYSTEM_USER_EMAIL = os.getenv("ARGUS_WEBHOOK_SYSTEM_USER_EMAIL", "linkedeye.webhook@argus.local").strip()
ARGUS_WEBHOOK_DEFAULT_ORG_SLUG = os.getenv("ARGUS_WEBHOOK_DEFAULT_ORG_SLUG", "").strip()

# Default monitoring URLs for asset bootstrap
ARGUS_DEFAULT_PROMETHEUS_URL = os.getenv("ARGUS_DEFAULT_PROMETHEUS_URL", "")
ARGUS_DEFAULT_GRAFANA_URL = os.getenv("ARGUS_DEFAULT_GRAFANA_URL", "")
ARGUS_DEFAULT_REDIS_URL = os.getenv("ARGUS_DEFAULT_REDIS_URL", REDIS_URL)
ARGUS_DEFAULT_ENTITY_HOST = os.getenv("ARGUS_DEFAULT_ENTITY_HOST", "")
ARGUS_DEFAULT_ENTITY_PORT = os.getenv("ARGUS_DEFAULT_ENTITY_PORT", "")

SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

