"""Branded transactional email.

``send_templated_email(to, "email/welcome", context)`` renders
``email/welcome_subject.txt``, ``email/welcome_message.txt`` and, when it
exists, ``email/welcome_message.html`` (extending ``email/base.html``), and
sends a multipart message through the configured backend (EMAIL_PROVIDER).
"""

from __future__ import annotations

import contextlib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string


def send_templated_email(to: str | list[str], prefix: str, context: dict | None = None) -> None:
    context = {"site_url": settings.SITE_URL, **(context or {})}
    subject = " ".join(render_to_string(f"{prefix}_subject.txt", context).split())
    text = render_to_string(f"{prefix}_message.txt", context)
    message = EmailMultiAlternatives(
        subject=f"{settings.ACCOUNT_EMAIL_SUBJECT_PREFIX}{subject}",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to] if isinstance(to, str) else to,
    )
    with contextlib.suppress(TemplateDoesNotExist):  # HTML part is optional
        message.attach_alternative(render_to_string(f"{prefix}_message.html", context), "text/html")
    message.send()
