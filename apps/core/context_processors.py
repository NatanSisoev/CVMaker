"""Template context shared by every page."""

from __future__ import annotations

from django.conf import settings


def site(request):
    return {"signup_mode": settings.SIGNUP_MODE}
