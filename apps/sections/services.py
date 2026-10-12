"""
Section-level domain services.

**Reordering** -- ``reorder_sections(cv, ordered_ids)`` and
``reorder_entries(section, ordered_ids)`` rewrite the ``order`` column on
``CVSection`` and ``SectionEntry`` rows in a single transaction. The
Editor's drag-reorder endpoints call these; tests pin the exact final order.

(YAML import used to live here as ``import_sections_from_data_model``; it is
now ``cv.importer.import_cv_from_yaml`` on rendercv 2.x.)

Services are side-effect-only -- they return ``None`` (or a created
object). They do not parse HTTP input, log to console, or render
templates. Views pass parsed input in and present output back.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Max

from .models import CVSection, Section, SectionEntry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cv.models import CV


# ---------------------------------------------------------------------------
# Reordering
# ---------------------------------------------------------------------------
@transaction.atomic
def reorder_sections(cv: CV, ordered_ids: Iterable) -> None:
    """Rewrite ``CVSection.order`` for ``cv`` to match ``ordered_ids``.

    ``ordered_ids`` is an iterable of section UUIDs in the desired final
    order (top of the CV first). Sections in ``cv`` not present in the
    iterable are left untouched -- the caller is expected to pass the
    full set when reordering.

    Raises ``CVSection.DoesNotExist`` if any id doesn't reference a
    section that's actually attached to this CV.
    """
    for index, section_id in enumerate(ordered_ids):
        # ``filter().update()`` would be one fewer query but loses the
        # DoesNotExist signal -- we'd silently no-op on a bad id.
        cv_section = CVSection.objects.get(cv=cv, section_id=_coerce_uuid(section_id))
        cv_section.order = index
        cv_section.save(update_fields=["order"])


@transaction.atomic
def reorder_entries(section: Section, ordered_ids: Iterable) -> None:
    """Rewrite ``SectionEntry.order`` for ``section`` to match ``ordered_ids``."""
    for index, entry_id in enumerate(ordered_ids):
        section_entry = SectionEntry.objects.get(section=section, entry_id=_coerce_uuid(entry_id))
        section_entry.order = index
        section_entry.save(update_fields=["order"])


def _coerce_uuid(value) -> uuid.UUID:
    """Accept either a UUID instance or a string; reject anything else."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


# ---------------------------------------------------------------------------
# Building a CV from the Editor
# ---------------------------------------------------------------------------
def _next_order(queryset) -> int:
    last = queryset.aggregate(last=Max("order"))["last"]
    return 0 if last is None else last + 1


@transaction.atomic
def attach_section_to_cv(cv: CV, section: Section) -> CVSection:
    """Append ``section`` to ``cv`` (no-op if it is already attached)."""
    link, _ = CVSection.objects.get_or_create(
        cv=cv,
        section=section,
        defaults={"order": _next_order(CVSection.objects.filter(cv=cv))},
    )
    return link


@transaction.atomic
def append_entry_to_section(section: Section, entry) -> SectionEntry:
    """Append ``entry`` to ``section`` (no-op if it is already in it)."""
    link, _ = SectionEntry.objects.get_or_create(
        section=section,
        entry=entry,
        defaults={"order": _next_order(SectionEntry.objects.filter(section=section))},
    )
    return link


def section_entry_kind(section: Section) -> str | None:
    """The ``type`` slug ("education", "bullet", ...) of the section's entries,
    or None while it is empty. rendercv allows one kind per section."""
    from entries.models import BaseEntry

    first = (
        BaseEntry.objects.filter(section_entries__section=section)
        .select_subclasses()
        .order_by("section_entries__order")
        .first()
    )
    return first.type if first else None
