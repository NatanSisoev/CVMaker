"""allauth hooks for CVMaker."""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request) -> bool:
        """``SIGNUP_MODE = "waitlist"`` closes signup; allauth then renders
        ``account/signup_closed.html`` (our waitlist form)."""
        return settings.SIGNUP_MODE == "open"
