import time
from django.core.cache import cache
from django.http import JsonResponse

class RateLimitMiddleware:
    """
    Simple per-tenant and per-user rate limiting.
    Limits: 
    - 100 requests per minute per user.
    - 5000 requests per hour per organization.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        user_id = request.user.id
        org_id = getattr(request, 'organization', None)
        org_id = org_id.id if org_id else 'anon'

        # User rate limit (1 min window)
        user_key = f"rl_user_{user_id}_{int(time.time() / 60)}"
        user_count = cache.get(user_key, 0)
        
        if user_count >= 100:
            return JsonResponse({
                "success": False,
                "error": "Rate limit exceeded (User). Please wait a minute.",
                "code": "RATE_LIMIT_USER"
            }, status=429)
            
        cache.set(user_key, user_count + 1, 60)

        # Organization rate limit (1 hour window)
        org_key = f"rl_org_{org_id}_{int(time.time() / 3600)}"
        org_count = cache.get(org_key, 0)
        
        if org_count >= 5000:
            return JsonResponse({
                "success": False,
                "error": "Organization hourly quota reached.",
                "code": "RATE_LIMIT_ORG"
            }, status=429)
            
        cache.set(org_key, org_count + 1, 3600)

        return self.get_response(request)
