"""Response-header middleware not covered by Django's SecurityMiddleware."""

from __future__ import annotations

from django.conf import settings


class PermissionsPolicyMiddleware:
    """Send ``Permissions-Policy`` (``settings.PERMISSIONS_POLICY``) on every response."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = getattr(settings, "PERMISSIONS_POLICY", "")

    def __call__(self, request):
        response = self.get_response(request)
        if self.policy:
            response.headers.setdefault("Permissions-Policy", self.policy)
        return response


class LimitExceededMiddleware:
    """Turn a plan-limit error raised anywhere into a friendly response:
    a flash + redirect for pages, a 403 JSON body for the API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.contrib import messages
        from django.http import JsonResponse
        from django.shortcuts import redirect

        from cv.models import LimitExceeded

        if not isinstance(exception, LimitExceeded):
            return None
        if request.path.startswith("/api/"):
            return JsonResponse({"detail": str(exception)}, status=403)
        messages.error(request, str(exception))
        return redirect("cv-list")
