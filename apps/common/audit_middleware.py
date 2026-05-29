import json

from django.http import RawPostDataException

from .audit import create_audit_log

class AuditLogMiddleware:
    """
    Automatically logs mutating requests (POST, PATCH, PUT, DELETE) 
    to the AuditLog model.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only log if user is authenticated and it's a mutating request
        if request.user.is_authenticated and request.method in ['POST', 'PATCH', 'PUT', 'DELETE']:
            # Skip some paths (like login which is logged manually, or the audit log itself)
            if '/api/v1/audit/' in request.path or '/api/v1/auth/login' in request.path:
                return response

            if 200 <= response.status_code < 600:
                resource_type, resource_id = self._resource_from_path(request.path)
                action = f"{request.method}_{resource_type}"
                if response.status_code >= 500:
                    action = f"{action}_FAILED"

                create_audit_log(
                    request,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=f"{request.method} request to {request.path}",
                    payload=self._request_payload(request),
                    response_payload={"status_code": response.status_code},
                    status_code=response.status_code,
                )

        return response

    @staticmethod
    def _resource_from_path(path):
        path_parts = [part for part in path.strip('/').split('/') if part]
        if len(path_parts) >= 2 and path_parts[0] == "api" and path_parts[1].startswith("v"):
            path_parts = path_parts[2:]

        resource_id = None
        resource_type = path_parts[-1].upper() if path_parts else "SYSTEM"
        if path_parts:
            last = path_parts[-1]
            looks_like_id = last.isdigit() or (len(last) == 36 and '-' in last)
            if looks_like_id and len(path_parts) >= 2:
                resource_id = last
                resource_type = path_parts[-2].upper()

        return resource_type, resource_id

    @staticmethod
    def _request_payload(request):
        if request.method == "DELETE":
            return None
        if request.POST:
            return request.POST
        content_type = (request.META.get("CONTENT_TYPE") or "").lower()
        if "application/json" not in content_type:
            return None
        try:
            body = request.body
        except RawPostDataException:
            return None
        if not body or len(body) > 100_000:
            return None
        try:
            return json.loads(body.decode(request.encoding or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
