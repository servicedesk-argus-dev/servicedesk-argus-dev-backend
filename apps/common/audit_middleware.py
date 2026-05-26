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

            # Only log successful or client-error requests (don't log server errors here, maybe)
            if 200 <= response.status_code < 500:
                action = f"{request.method}_{request.path.split('/')[-2].upper()}"
                resource_type = request.path.split('/')[-2].upper()
                
                # Try to extract ID if it's a detail view
                resource_id = None
                path_parts = request.path.strip('/').split('/')
                if path_parts[-1].isdigit() or (len(path_parts[-1]) == 36 and '-' in path_parts[-1]):
                    resource_id = path_parts[-1]
                    resource_type = path_parts[-2].upper()

                create_audit_log(
                    request,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=f"{request.method} request to {request.path}"
                )

        return response
