import uuid
from collections.abc import Mapping

from .models import AuditLog


MASKED_VALUE = "***REDACTED***"
MAX_AUDIT_STRING_LENGTH = 2000
MAX_AUDIT_DEPTH = 6

SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "apikey",
    "mfa",
    "otp",
    "totp",
    "credential",
    "private_key",
)


def _is_sensitive_key(key):
    normalized = str(key or "").strip().lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def sanitize_audit_payload(value, depth=0):
    """Return a JSON-safe payload with credentials and large values removed."""
    if value is None:
        return None
    if depth > MAX_AUDIT_DEPTH:
        return "[MAX_DEPTH]"

    if hasattr(value, "dict") and callable(value.dict):
        value = value.dict()

    if isinstance(value, Mapping):
        return {
            str(key): MASKED_VALUE if _is_sensitive_key(key) else sanitize_audit_payload(item, depth + 1)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [sanitize_audit_payload(item, depth + 1) for item in value]

    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > MAX_AUDIT_STRING_LENGTH:
            return f"{value[:MAX_AUDIT_STRING_LENGTH]}...[TRUNCATED]"
        return value

    return str(value)[:MAX_AUDIT_STRING_LENGTH]


def _correlation_id(request, explicit=None):
    if explicit:
        return str(explicit)[:100]

    existing = getattr(request, "audit_correlation_id", None)
    if existing:
        return existing

    header_value = (
        request.META.get("HTTP_X_CORRELATION_ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("HTTP_CF_RAY")
    )
    value = str(header_value or uuid.uuid4())[:100]
    setattr(request, "audit_correlation_id", value)
    return value


def create_audit_log(
    request,
    action,
    resource_type,
    resource_id=None,
    description="",
    organization=None,
    payload=None,
    response_payload=None,
    status_code=None,
    method=None,
    path=None,
    actor_email=None,
    correlation_id=None,
):
    """
    Creates an audit log entry.
    """
    org = organization or getattr(request, "organization", None)
    user = getattr(request, "user", None)
    if not org and getattr(user, "is_authenticated", False):
        org = getattr(user, "organization", None)
    
    # If still no org, but we have a user, try to get it from the user
    # (Useful for login events where the user is found but not yet in request.user)
    # Note: We'll handle this in the caller for now.


    # Get IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    if not actor_email and getattr(user, "is_authenticated", False):
        actor_email = getattr(user, "email", None) or getattr(user, "username", "")

    return AuditLog.objects.create(
        organization=org,
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        description=description,
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT'),
        actor_email=actor_email or "",
        method=(method or request.method or "").upper()[:10],
        path=(path or request.path or "")[:512],
        status_code=status_code,
        correlation_id=_correlation_id(request, correlation_id),
        request_payload=sanitize_audit_payload(payload),
        response_payload=sanitize_audit_payload(response_payload),
    )
