"""
Shared model mixins.

Every app-level model should inherit from one of these. Keeps the timestamp
and UUID PK conventions consistent across the codebase.
"""

from __future__ import annotations

import uuid

from django.db import models


class TimestampedModel(models.Model):
    """Adds ``created_at`` and ``updated_at`` auto-managed columns."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """PK is a UUID4; safer than auto-incrementing ints for user-facing URLs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class UUIDTimestampedModel(UUIDModel, TimestampedModel):
    """Most app models want both — this is the default base class."""

    class Meta:
        abstract = True
