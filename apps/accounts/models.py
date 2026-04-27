"""
Custom user model.

Uses ``email`` as the login identifier (``USERNAME_FIELD``). Keeps
``username`` as an optional display handle that defaults to the local part
of the email. Swapped in now, pre-launch, because adding a custom user model
after data exists is a multi-day migration.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager["User"]):
    """Manager that creates users keyed by email (not username)."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> User:
        if not email:
            raise ValueError("An email address is required to create a user.")
        email = self.normalize_email(email)
        # Default the username to the local part of the email if not supplied.
        # AbstractUser still requires username to be unique; we enforce uniqueness
        # but hide the field in most UIs.
        extra_fields.setdefault("username", email.split("@", 1)[0])
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> User:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Application user. ``email`` is the identifier; ``username`` is optional
    and mostly legacy. Every new field lives here — don't create a separate
    Profile model unless there's a strong reason (FK sprawl costs more than
    a few columns do).
    """

    email = models.EmailField(_("email address"), unique=True)

    # Display name — optional; falls back to username or email.
    display_name = models.CharField(
        _("display name"),
        max_length=150,
        blank=True,
        help_text=_("Shown on your public profile if you enable one."),
    )

    # i18n preferences
    preferred_language = models.CharField(
        _("preferred language"),
        max_length=5,
        default="en",
        help_text=_("BCP-47 tag. Used for the UI and as the default CV language."),
    )

    # Timestamps (superseding AbstractUser's date_joined for consistency)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]  # asked by createsuperuser after email

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self) -> str:
        return self.email

    def get_display_name(self) -> str:
        return self.display_name or self.username or self.email.split("@", 1)[0]
