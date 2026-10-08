"""Import a rendercv 2.x YAML file into CVMaker rows.

``import_cv_from_yaml(user, yaml_text, alias)`` validates the file with
rendercv itself (so users get rendercv's own error messages), then creates a
CVInfo, a CVDesign, the CV, one Section per rendercv section and one entry
row per rendercv entry -- all in a single transaction, so a failed import
leaves nothing behind.

rendercv detects each section's entry type; we map it onto our entry model
with ``get_entry_model``. Field shapes differ in a few places:

- dates: rendercv accepts ``YYYY-MM-DD``, ``YYYY-MM``, ``YYYY`` or ``present``;
  we store ``DateField``s, so partial dates take day/month 1 and ``present``
  (or anything unparseable) becomes empty.
- list fields (``highlights``, ``authors``): joined with ``; `` / ``, `` --
  the separators our serializers split on.
- photo and custom connections are not imported (no file to attach; no column).
"""

from __future__ import annotations

import datetime
import re

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.text import slugify

from core.rendercv import format_validation_errors

from .models import CV, CVDesign, CVInfo

_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$")
_SKIP_FIELDS = {"id", "user", "alias", "translations", "canonical_language", "baseentry_ptr"}
_LIST_SEPARATORS = {"authors": ", "}
_ALIAS_MAX = 20


class CVImportError(ValueError):
    """User-readable import failure; the message is shown as-is."""


def import_cv_from_yaml(user, yaml_text: str, alias: str) -> CV:
    model = _validate(yaml_text)
    alias = _alias(alias)

    with transaction.atomic():
        info = _save(CVInfo(user=user, alias=alias, **_info_fields(model.cv)), "personal info")
        theme = getattr(model.design, "theme", None)
        valid_themes = {value for value, _ in CVDesign.THEME_CHOICES if value != "custom"}
        design = _save(
            CVDesign(user=user, alias=alias, theme=theme if theme in valid_themes else "classic"),
            "design",
        )
        cv = _save(CV(user=user, alias=alias, info=info, design=design), "CV")
        _import_sections(user, cv, model.cv.rendercv_sections, alias)
    return cv


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate(yaml_text: str):
    from rendercv.exception import RenderCVUserError, RenderCVUserValidationError
    from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model

    if not yaml_text.strip():
        raise CVImportError("The file is empty.")
    try:
        _, model = build_rendercv_dictionary_and_model(yaml_text)
    except RenderCVUserValidationError as exc:
        raise CVImportError(
            format_validation_errors(exc, "This file is not a valid rendercv CV:")
        ) from exc
    except RenderCVUserError as exc:
        raise CVImportError(exc.message or "rendercv could not read this file.") from exc
    return model


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------
def _info_fields(cv_model) -> dict:
    def first(value):
        if isinstance(value, list):
            value = value[0] if value else None
        return str(value) if value is not None else None

    networks = {sn.network: sn.username for sn in (cv_model.social_networks or [])}
    return {
        "name": cv_model.name,
        "location": cv_model.location,
        "email": first(cv_model.email),
        "phone": _phone(first(cv_model.phone)),
        "website": first(cv_model.website),
        "social_networks": networks or None,
    }


def _phone(value: str | None) -> str | None:
    # rendercv normalises phones to tel: URIs (tel:+1-609-...); keep the number.
    return value.removeprefix("tel:") if value else value


def _import_sections(user, cv, rendercv_sections, alias: str) -> None:
    from entries.models import get_entry_model
    from sections.models import CVSection, Section, SectionEntry

    for order, rc_section in enumerate(rendercv_sections, start=1):
        section = _save(
            Section(user=user, title=rc_section.title, alias=_alias(rc_section.title)),
            f"section {rc_section.title!r}",
        )
        CVSection.objects.create(cv=cv, section=section, order=order)

        entry_model = get_entry_model(rc_section.entry_type)
        for entry_order, rc_entry in enumerate(rc_section.entries, start=1):
            where = f"{rc_section.title!r} entry {entry_order}"
            entry = entry_model(
                user=user,
                alias=_alias(f"{section.alias}-{entry_order}"),
                **_entry_fields(entry_model, rc_entry, where),
            )
            _save(entry, where)
            SectionEntry.objects.create(section=section, entry=entry, order=entry_order)


def _entry_fields(entry_model, rc_entry, where: str) -> dict:
    if isinstance(rc_entry, str):  # TextEntry
        return {"text": rc_entry}

    data = rc_entry.model_dump(exclude_none=True)
    fields = {}
    for field in entry_model._meta.concrete_fields:
        if field.name in _SKIP_FIELDS or field.name not in data:
            continue
        value = data[field.name]
        if isinstance(field, models.DateField):
            value = _parse_date(value)
        elif isinstance(value, list):
            value = _LIST_SEPARATORS.get(field.name, "; ").join(str(v) for v in value)
        else:
            value = str(value)
        if value is not None:
            fields[field.name] = value
    return fields


def _parse_date(value) -> datetime.date | None:
    match = _DATE_RE.match(str(value).strip())
    if not match:
        return None  # "present", free text like "Fall 2023"
    year, month, day = (int(part) if part else 1 for part in match.groups())
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _save(instance, where: str):
    try:
        instance.full_clean(exclude=["user"])
    except ValidationError as exc:
        problems = "; ".join(
            f"{field}: {' '.join(messages)}" for field, messages in exc.message_dict.items()
        )
        raise CVImportError(f"Could not import {where}: {problems}") from exc
    instance.save()
    return instance


def _alias(text: str) -> str:
    return (slugify(text) or "imported")[:_ALIAS_MAX].rstrip("-") or "imported"
