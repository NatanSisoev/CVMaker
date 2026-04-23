"""
WSGI config for cvmaker.

Exposes the WSGI callable as a module-level variable named ``application``.
Gunicorn loads this in production.
"""
from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cvmaker.settings.prod")

application = get_wsgi_application()
