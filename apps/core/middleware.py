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
