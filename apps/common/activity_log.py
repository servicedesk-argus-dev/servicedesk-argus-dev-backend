"""Centralized activity rows with optional client IP / user-agent for audit."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str | None:
    """Best-effort client IP; honors X-Forwarded-For only when proxy is trusted."""
    from django.conf import settings

    trusted = getattr(settings, "TRUSTED_PROXY_IPS", ()) or ()
    remote = request.META.get("REMOTE_ADDR")
    if trusted and remote in trusted:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
    return remote


def create_activity(*, request: HttpRequest | None = None, **kwargs: Any):
    """Create an Activity row; pass ``request`` to capture IP and User-Agent."""
    from apps.incidents.models import Activity

    if request is not None:
        kwargs.setdefault("actor_ip", get_client_ip(request))
        ua = request.META.get("HTTP_USER_AGENT") or ""
        kwargs.setdefault("user_agent", ua[:512])
    return Activity.objects.create(**kwargs)
