"""
Section + SectionEntry models.

A ``Section`` is a user-owned, named bag of entries (e.g. "Education",
"Publications"). A ``CVSection`` joins a section onto a CV with an order.
A ``SectionEntry`` joins a single entry onto a section with an order.

Phase 2.1 simplification (ADR-0005):

  Old: ``SectionEntry`` pointed at entries via a GenericForeignKey through
       ``ContentType``, with a project-wide ``pre_delete`` signal cleaning
       up dangling rows when a subclass entry was deleted.
  New: ``SectionEntry.entry`` is a direct FK to ``BaseEntry``. Postgres
       enforces referential integrity; cascade deletes happen at the DB
       layer; the signal is gone.

Subclass promotion (resolving an ``EducationEntry`` from a ``BaseEntry``
row) is handled by ``model_utils.InheritanceManager.select_subclasses()``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from entries.models import BaseEntry

if TYPE_CHECKING:
    from collections.abc import Iterable


class CVSection(models.Model):
    """Through-table joining a CV to a Section with an order."""

    cv = models.ForeignKey("cv.CV", on_delete=models.CASCADE)
    section = models.ForeignKey("sections.Section", on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = ("cv", "section")

    def __str__(self) -> str:
        return f"CVSection(cv={self.cv_id}, section={self.section_id}, order={self.order})"


class Section(models.Model):
    """A user-owned ordered collection of entries.

    The same section can be reused across multiple CVs via ``CVSection``.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="cv_sections",
    )
    title = models.CharField(max_length=50, help_text="Name of the section")
    alias = models.CharField(max_length=20, help_text="Alias for the section", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    def __str__(self) -> str:
        return f"Section({self.title!r}, alias={self.alias!r})"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def serialize(self, language: str | None = None) -> list[dict]:
        """Render every entry in this section, in order, in ``language``.

        ``language`` is an ISO 639-1 code or ``None``. ``None`` means "use
        the entry's canonical language" (no translation). Missing
        translations fall back to canonical per ADR-0006.

        Resolves subclass instances via ``select_subclasses()`` so each
        ``BaseEntry`` is materialized as its concrete type and the right
        ``serialize`` override is called.
        """
        ordered_entry_ids = list(
            self.section_entries.order_by("order").values_list("entry_id", flat=True)
        )
        if not ordered_entry_ids:
            return []

        promoted = _promote_in_order(ordered_entry_ids)
        return [entry.serialize(language=language) for entry in promoted]


class SectionEntry(models.Model):
    """One entry's slot inside a section, with an order.

    A single ``BaseEntry`` row can be referenced by many ``SectionEntry``
    rows (across sections / across users' shared sections), but in
    practice each entry usually appears in one section. Cascade deletes
    travel from ``BaseEntry`` → ``SectionEntry`` automatically.
    """

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="section_entries",
    )
    entry = models.ForeignKey(
        BaseEntry,
        on_delete=models.CASCADE,
        related_name="section_entries",
    )
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = ("section", "entry")

    def __str__(self) -> str:
        return f"SectionEntry(section={self.section_id}, entry={self.entry_id}, order={self.order})"

    def serialize(self, language: str | None = None) -> dict:
        """Promote ``self.entry`` to its concrete subclass and serialize."""
        return self.real_entry.serialize(language=language)

    @property
    def real_entry(self) -> BaseEntry:
        """Return ``self.entry`` promoted to its concrete MTI subclass.

        Use this in templates and one-off view code where the
        polymorphic instance is needed -- it costs one query per access
        and is meant for small N. For loops over many SectionEntry
        rows, prefer ``Section.serialize()`` or
        ``BaseEntry.objects.filter(pk__in=...).select_subclasses()`` to
        amortize.
        """
        return BaseEntry.objects.select_subclasses().get(pk=self.entry_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _promote_in_order(entry_ids: Iterable) -> list[BaseEntry]:
    """Fetch the BaseEntry rows for ``entry_ids`` promoted to subclasses,
    preserving the order of ``entry_ids``.

    One DB hit (plus subclass LEFT JOINs) regardless of how many entries
    are involved -- preferable to N+1 calls of ``.entry``.
    """
    entry_ids = list(entry_ids)
    by_id = {e.pk: e for e in BaseEntry.objects.filter(pk__in=entry_ids).select_subclasses()}
    return [by_id[pk] for pk in entry_ids if pk in by_id]


# ---------------------------------------------------------------------------
# SectionManager — imports CV-shaped YAML into Section/SectionEntry rows.
# Phase 2.3 moves this to ``apps/sections/services.py`` and shrinks the
# import view in apps/cv/views.py to a single service call.
# ---------------------------------------------------------------------------
class SectionManager:
    """Materialize Section + SectionEntry rows from a parsed rendercv data
    model, used by the import flow in ``apps/cv/views.py``.

    Lives on the model module for now to preserve the import surface; will
    move to ``apps/sections/services.py`` in Phase 2.3.
    """

    def __init__(self, user, cv, data_model, alias):
        self.user = user
        self.cv = cv
        self.data_model = data_model
        self.alias = alias

    def create_all_sections(self):
        """Create every section in the data model, in order."""
        if not hasattr(self.data_model.cv, "sections"):
            return

        for order, section in enumerate(self.data_model.cv.sections, start=1):
            self._create_section(section, order)

    # ------------------------------------------------------------------
    # Per-section helpers
    # ------------------------------------------------------------------
    def _create_section(self, section_data, order):
        # Avoid the cv.models import at module load time (cv.models imports
        # entries.models, entries.models has no circular need but keeping
        # imports lazy keeps the dependency graph one-directional).
        section = Section.objects.create(user=self.user, title=section_data.title, alias=self.alias)
        CVSection.objects.create(cv=self.cv, section=section, order=order)
        self._create_entries(section, section_data)

    def _create_entries(self, section, section_data):
        if not hasattr(section_data, "entries") or not section_data.entries:
            return

        # Lazy import to avoid hard-wiring the entries app at module load.
        from entries.models import get_entry_model

        entry_model = get_entry_model(section_data.entry_type)

        for entry_order, entry_data in enumerate(section_data.entries, start=1):
            payload = {k: v for k, v in entry_data.dict().items() if v is not None}
            entry_instance = entry_model.objects.create(user=self.user, alias=self.alias, **payload)
            SectionEntry.objects.create(
                section=section,
                entry=entry_instance,  # FK to BaseEntry; subclass row matches via MTI parent
                order=entry_order,
            )
