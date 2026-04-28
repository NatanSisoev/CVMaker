"""
Section-level domain services.

Two responsibilities:

  1. **Reordering** -- ``reorder_sections(cv, ordered_ids)`` and
     ``reorder_entries(section, ordered_ids)`` rewrite the ``order``
     column on ``CVSection`` and ``SectionEntry`` rows in a single
     transaction. The HTMX drag-drop UI in Phase 4 calls these from the
     view; tests pin the exact final order under reordering.

  2. **Bulk import from a rendercv data model** --
     ``import_sections_from_data_model(user, cv, data_model, alias)``
     walks a parsed rendercv YAML structure and creates the matching
     Section + SectionEntry rows. Replaces the ``SectionManager`` class
     that lived on ``apps/sections/models.py`` through Phase 2.1.

Services are side-effect-only -- they return ``None`` (or a created
object). They do not parse HTTP input, log to console, or render
templates. Views pass parsed input in and present output back.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.db import transaction

from .models import CVSection, Section, SectionEntry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.contrib.auth.models import AbstractBaseUser

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
# Bulk import from a parsed rendercv data model
# ---------------------------------------------------------------------------
@transaction.atomic
def import_sections_from_data_model(
    user: AbstractBaseUser,
    cv: CV,
    data_model,
    alias: str,
) -> None:
    """Create ``Section`` + ``SectionEntry`` rows from a rendercv data model.

    Used by the YAML import flow in ``apps/cv/views.py``. Replaces the
    ``SectionManager`` class that lived on ``sections/models.py`` through
    Phase 2.1 -- same logic, now reachable as a top-level callable that
    tests can call directly without a class instantiation dance.
    """
    if not hasattr(data_model.cv, "sections"):
        return

    # Lazy import: keeps sections.services from importing entries at
    # module-load time, which would create a cv -> sections -> entries
    # dependency chain that complicates the apps/__init__ load order.
    from entries.models import get_entry_model

    for order, section_data in enumerate(data_model.cv.sections, start=1):
        section = Section.objects.create(user=user, title=section_data.title, alias=alias)
        CVSection.objects.create(cv=cv, section=section, order=order)

        if not getattr(section_data, "entries", None):
            continue

        entry_model = get_entry_model(section_data.entry_type)
        for entry_order, entry_data in enumerate(section_data.entries, start=1):
            payload = {k: v for k, v in entry_data.dict().items() if v is not None}
            entry_instance = entry_model.objects.create(user=user, alias=alias, **payload)
            SectionEntry.objects.create(
                section=section,
                entry=entry_instance,
                order=entry_order,
            )
