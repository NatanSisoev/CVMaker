"""
ASGI config for cvmaker.

Exposes the ASGI callable as a module-level variable named ``application``.
Uvicorn loads this in production for async + HTMX support.
"""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cvmaker.settings.prod")

application = get_asgi_application()
