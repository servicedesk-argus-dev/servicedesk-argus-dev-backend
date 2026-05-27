from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import socketio
except Exception:  # pragma: no cover - keeps management commands usable before deps install
    socketio = None


SOCKET_PATH = "socket.io"
SOCKET_REDIS_URL = getattr(settings, "SOCKETIO_REDIS_URL", None) or getattr(settings, "REDIS_URL", None)


def _cors_allowed_origins() -> list[str] | str:
    origins = list(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or [])
    if origins:
        return origins
    return "*" if getattr(settings, "DEBUG", False) else []


def _build_async_server():
    if socketio is None:
        return None
    try:
        manager = socketio.AsyncRedisManager(SOCKET_REDIS_URL) if SOCKET_REDIS_URL else None
    except Exception:
        logger.exception("Unable to configure Socket.IO Redis manager")
        manager = None
    return socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=_cors_allowed_origins(),
        client_manager=manager,
        logger=False,
        engineio_logger=False,
    )


sio = _build_async_server()
_write_manager = None


def _get_write_manager():
    global _write_manager
    if socketio is None or not SOCKET_REDIS_URL:
        return None
    if _write_manager is None:
        _write_manager = socketio.RedisManager(SOCKET_REDIS_URL, write_only=True)
    return _write_manager


def _user_from_token(token: str):
    from rest_framework_simplejwt.tokens import AccessToken

    from apps.accounts.models import User

    access = AccessToken(token)
    user_id = access.get("user_id")
    if not user_id:
        return None
    return (
        User.objects.select_related("organization")
        .prefetch_related("roles", "roles__permissions")
        .filter(id=user_id, is_active=True, is_active_member=True)
        .first()
    )


async def _load_user(token: str):
    return await sync_to_async(_user_from_token, thread_sensitive=True)(token)


if sio is not None:

    @sio.event
    async def connect(sid, environ, auth):  # noqa: ANN001
        token = ""
        if isinstance(auth, dict):
            token = str(auth.get("token") or "")
        if not token:
            query = environ.get("QUERY_STRING") or ""
            for pair in query.split("&"):
                key, _, value = pair.partition("=")
                if key == "token":
                    token = value
                    break
        if not token:
            raise ConnectionRefusedError("missing token")

        user = await _load_user(token)
        if user is None:
            raise ConnectionRefusedError("invalid token")

        from apps.common.permissions import is_service_desk_staff

        await sio.save_session(
            sid,
            {
                "user_id": str(user.id),
                "organization_id": str(user.organization_id) if user.organization_id else None,
            },
        )
        await sio.enter_room(sid, f"user:{user.id}")
        if user.organization_id:
            await sio.enter_room(sid, f"org:{user.organization_id}")
        if await sync_to_async(is_service_desk_staff, thread_sensitive=True)(user):
            await sio.enter_room(sid, "staff")

    @sio.event
    async def disconnect(sid):  # noqa: ANN001
        return None


def create_socketio_application(django_application):
    if sio is None:
        return django_application
    return socketio.ASGIApp(sio, django_application, socketio_path=SOCKET_PATH)


def _emit(event: str, payload: dict[str, Any], *, room: str) -> None:
    manager = _get_write_manager()
    if manager is None:
        return
    try:
        manager.emit(event, payload, room=room)
    except Exception:
        logger.exception("Socket.IO emit failed for %s to %s", event, room)


def emit_to_user(user_id: object, event: str, payload: dict[str, Any]) -> None:
    if user_id:
        _emit(event, payload, room=f"user:{user_id}")


def emit_to_org(organization_id: object, event: str, payload: dict[str, Any]) -> None:
    if organization_id:
        _emit(event, payload, room=f"org:{organization_id}")


def emit_to_staff(event: str, payload: dict[str, Any]) -> None:
    _emit(event, payload, room="staff")


def notification_payload(notification, *, unread_count: int | None = None) -> dict[str, Any]:
    if unread_count is None:
        unread_count = (
            notification.user.notifications.filter(is_read=False).count()
            if getattr(notification, "user_id", None)
            else 0
        )
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "isRead": notification.is_read,
        "readAt": notification.read_at.isoformat() if notification.read_at else None,
        "channel": notification.channel,
        "createdAt": notification.created_at.isoformat() if notification.created_at else None,
        "unreadCount": unread_count,
    }


def emit_notification(notification, *, event: str = "notification:new", unread_count: int | None = None) -> None:
    emit_to_user(notification.user_id, event, notification_payload(notification, unread_count=unread_count))


def emit_notification_read(user_id: object, notification_id: object, *, unread_count: int, read_at=None) -> None:
    emit_to_user(
        user_id,
        "notification:read",
        {
            "id": str(notification_id),
            "isRead": True,
            "readAt": read_at.isoformat() if read_at else None,
            "unreadCount": unread_count,
        },
    )


def emit_notifications_read_all(user_id: object) -> None:
    emit_to_user(user_id, "notifications:read-all", {"unreadCount": 0})


def record_payload(record, action: str) -> dict[str, Any]:
    organization_id = getattr(record, "organization_id", None)
    return {
        "id": str(getattr(record, "id", "")),
        "number": getattr(record, "number", None) or getattr(record, "alert_id", None) or str(getattr(record, "id", "")),
        "organizationId": str(organization_id) if organization_id else None,
        "action": action,
    }


def emit_record_event(resource: str, record, action: str = "updated") -> None:
    event = f"{resource}:{action}"
    if resource == "alert" and action == "updated":
        event = "alert:fired"
    if resource == "asset":
        event = "asset:updated"
    if resource == "learning":
        event = "learning:updated"
    payload = record_payload(record, action)
    emit_to_staff(event, payload)
    emit_to_org(getattr(record, "organization_id", None), event, payload)

