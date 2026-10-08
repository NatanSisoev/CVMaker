"""Account signal handlers."""

from __future__ import annotations

from allauth.account.signals import email_confirmed
from django.dispatch import receiver

from core.email import send_templated_email


@receiver(email_confirmed)
def send_welcome_on_first_confirmation(request, email_address, **kwargs):
    """Welcome a new user once -- when their first address is verified, not on
    every later email change."""
    verified = email_address.user.emailaddress_set.filter(verified=True)
    if verified.count() == 1:
        send_templated_email(email_address.email, "email/welcome")
