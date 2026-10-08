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
