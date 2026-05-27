from .models import AuditLog

def create_audit_log(request, action, resource_type, resource_id=None, description="", organization=None, payload=None):
    """
    Creates an audit log entry.
    """
    org = organization or getattr(request, "organization", None)
    if not org and request.user.is_authenticated:
        org = getattr(request.user, "organization", None)
    
    # If still no org, but we have a user, try to get it from the user
    # (Useful for login events where the user is found but not yet in request.user)
    # Note: We'll handle this in the caller for now.


    # Get IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    return AuditLog.objects.create(
        organization=org,
        user=request.user if request.user.is_authenticated else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        description=description,
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT'),
        request_payload=payload
    )
