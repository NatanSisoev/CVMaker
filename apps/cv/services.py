"""
CV-level domain services.

The home for behavior that doesn't belong on a single model:

  - ``build_render_payload(cv, language=None, style=None)`` -- assemble
    the dict that gets handed to rendercv. Today this is a thin wrapper
    over ``CV.serialize()``; tomorrow (Phase 3) it takes ``style``
    overrides and returns the full rendercv data model.
  - ``clone_cv(cv, new_alias)`` -- create a new CV that points at the
    same Sections as the source, with copies of the per-CV singletons
    (CVInfo, CVDesign, CVLocale, CVSettings) and the same ordering of
    sections.

By convention, services don't touch ``request`` -- they operate on
domain objects. Views are responsible for parsing input, calling
services, and rendering responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from sections.models import CVSection

from .models import CV, CVDesign, CVInfo, CVLocale, CVSettings

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Render payload
# ---------------------------------------------------------------------------
def build_render_payload(
    cv: CV,
    language: str | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """Return the rendercv-ready payload for ``cv``.

    Parameters
    ----------
    cv : CV
        The CV instance to render.
    language : str, optional
        ISO 639-1 code. If ``None``, defaults to ``cv.locale.language``
        (which itself may be ``None``, meaning "use each entry's
        canonical language").
    style : str, optional
        Phase 3 plug-point for design overrides. Currently ignored.

    The function is side-effect free apart from the ``pprint`` debug
    line in ``CV.serialize`` (Phase 3 strips that). Cache safe -- two
    calls with the same args should produce equal dicts.
    """
    # Allow callers to override the CV's default language without saving
    # CVLocale changes. Useful for "preview in Spanish" buttons.
    if language is not None:
        # Temporarily shadow cv.locale.language. We don't save -- just
        # let CV.serialize observe the override through the locale FK.
        original = getattr(cv.locale, "language", None) if cv.locale else None
        if cv.locale and original != language:
            cv.locale.language = language
            try:
                return cv.serialize()
            finally:
                cv.locale.language = original
    return cv.serialize()


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------
@transaction.atomic
def clone_cv(cv: CV, new_alias: str) -> CV:
    """Duplicate ``cv`` under ``new_alias`` for the same user.

    Strategy:

      - The four per-CV singletons (CVInfo, CVDesign, CVLocale, CVSettings)
        are *copied* -- a fresh row each, so edits to the clone don't
        bleed back into the source.
      - Sections are *shared* -- they're user-owned objects that can
        legitimately appear in multiple CVs (e.g. one "Education"
        section used by both an academic CV and an industry CV).
      - The CV-Section through rows (``CVSection``) are re-created so
        the clone has its own ordering.

    Wrapped in ``@transaction.atomic`` so a partial clone never lands.
    """
    new_cv = CV.objects.create(
        user=cv.user,
        alias=new_alias,
        info=_copy_or_none(cv.info, CVInfo),
        design=_copy_or_none(cv.design, CVDesign),
        locale=_copy_or_none(cv.locale, CVLocale),
        settings=_copy_or_none(cv.settings, CVSettings),
    )

    # Re-create the CVSection rows pointing at the same Section objects.
    for cv_section in CVSection.objects.filter(cv=cv).order_by("order"):
        CVSection.objects.create(
            cv=new_cv,
            section=cv_section.section,
            order=cv_section.order,
        )

    return new_cv


def _copy_or_none(instance, model_class):
    """Save a copy of ``instance`` (Django row clone idiom: pk=None).

    Re-fetches the row before mutating so we don't clobber the caller's
    Python reference. Naive ``instance.pk = None; instance.save()`` works
    for the DB but leaves the caller holding a Python object whose
    in-memory pk has silently shifted to the clone -- a recipe for
    next-step bugs.
    """
    if instance is None:
        return None
    fresh = model_class.objects.get(pk=instance.pk)
    fresh.pk = None
    fresh._state.adding = True
    fresh.save()
    return fresh


def language_status(cv: CV) -> list[dict]:
    """Per-language translation completeness for the entries in ``cv``.

    Returns ``[{"code", "done", "total"}, ...]``, active locale first, then
    alphabetical. Codes are the union of the locale's language, every entry's
    canonical language, and every translation key (all renderable: missing
    translations fall back to canonical at render time, ADR-0006).

    An entry counts as done for a language when it is the entry's canonical
    language, or when the translation bag has a key for every translatable
    field whose canonical value is non-empty (an explicit "" is an intentional
    translation, matching ``BaseEntry.get_field``).
    """
    from entries.models import BaseEntry

    entries = list(
        BaseEntry.objects.filter(section_entries__section__cvsection__cv=cv)
        .distinct()
        .select_subclasses()
    )
    codes: set[str] = set()
    for entry in entries:
        codes.add(entry.canonical_language)
        codes.update(entry.translations or {})
    active = cv.locale.language if cv.locale_id else None
    if active:
        codes.add(active)

    def done_in(entry, code: str) -> bool:
        if entry.canonical_language == code:
            return True
        bag = (entry.translations or {}).get(code)
        if not isinstance(bag, dict):
            return False
        return all(field in bag for field in entry.TRANSLATABLE_FIELDS if getattr(entry, field, ""))

    return [
        {"code": code, "done": sum(done_in(e, code) for e in entries), "total": len(entries)}
        for code in sorted(codes, key=lambda c: (c != active, c))
    ]


def available_languages(cv: CV) -> list[str]:
    """ISO 639-1 codes the CV can be rendered in, active locale first."""
    return [status["code"] for status in language_status(cv)]
