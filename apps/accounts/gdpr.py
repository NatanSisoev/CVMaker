"""GDPR: export everything we hold about a user; hard-delete an account.

Export is a single JSON document a user can download from Settings. It holds
everything they authored, but no secrets (password hash, API token) and no
binary files (PDFs/photos are listed by name only).

Deletion is a hard delete. Rows go through the ``on_delete=CASCADE`` chain
from ``User``; stored *files* do not -- Django never deletes a FileField's
file when its row goes -- so they are removed from storage first,
explicitly, and best-effort (a missing file must not block deletion).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

logger = logging.getLogger(__name__)

EXPORT_FORMAT_VERSION = 1


def export_user_data(user) -> dict[str, Any]:
    from cv.models import CV, CVDesign, CVInfo, CVLocale, CVSettings
    from entries.models import BaseEntry
    from rendering.models import Render
    from sections.models import Section

    def rows(qs, exclude=("user",)):
        out = []
        for obj in qs:
            data = model_to_dict(obj, exclude=list(exclude))
            for key, value in list(data.items()):
                if hasattr(value, "name"):  # FieldFile -> stored name (or None)
                    data[key] = value.name or None
            data["id"] = str(obj.pk)
            out.append(data)
        return out

    entries = []
    for entry in BaseEntry.objects.filter(user=user).select_subclasses().order_by("alias"):
        data = model_to_dict(entry, exclude=["user", "id", "baseentry_ptr"])
        entries.append({"id": str(entry.pk), "type": entry.type, **data})

    sections = [
        {
            "id": str(s.pk),
            "title": s.title,
            "alias": s.alias,
            "entries": [str(se.entry_id) for se in s.section_entries.all()],
        }
        for s in Section.objects.filter(user=user).prefetch_related("section_entries")
    ]

    cvs = []
    for cv in CV.objects.filter(user=user).order_by("created_date"):
        cvs.append(
            {
                "id": str(cv.pk),
                "alias": cv.alias,
                "created_date": cv.created_date,
                "modified_date": cv.modified_date,
                "info": str(cv.info_id) if cv.info_id else None,
                "design": str(cv.design_id) if cv.design_id else None,
                "locale": str(cv.locale_id) if cv.locale_id else None,
                "settings": str(cv.settings_id) if cv.settings_id else None,
                "sections": [
                    str(pk)
                    for pk in cv.sections.order_by("cvsection__order").values_list("id", flat=True)
                ],
            }
        )

    renders = [
        {
            "id": str(r.pk),
            "cv": str(r.cv_id),
            "language": r.language,
            "style": r.style,
            "status": r.status,
            "requested_at": r.requested_at,
            "completed_at": r.completed_at,
            "pdf_file": r.pdf_file.name or None,
        }
        for r in Render.objects.filter(cv__user=user).order_by("requested_at")
    ]

    return {
        "format": "cvmaker-export",
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": timezone.now(),
        "account": {
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "preferred_language": user.preferred_language,
            "date_joined": user.date_joined,
        },
        "cvs": cvs,
        "sections": sections,
        "entries": entries,
        "personal_info": rows(CVInfo.objects.filter(user=user)),
        "designs": rows(CVDesign.objects.filter(user=user)),
        "locales": rows(CVLocale.objects.filter(user=user)),
        "settings": rows(CVSettings.objects.filter(user=user)),
        "renders": renders,
    }


def _stored_files(user):
    """Every FieldFile owned by the user that points at a stored file."""
    from cv.models import CVDesign, CVInfo, CVLocale, CVSettings
    from rendering.models import Render

    sources = (
        (CVInfo.objects.filter(user=user), "photo"),
        (CVDesign.objects.filter(user=user), "design_file"),
        (CVLocale.objects.filter(user=user), "locale_file"),
        (CVSettings.objects.filter(user=user), "settings_file"),
        (Render.objects.filter(cv__user=user), "pdf_file"),
    )
    for qs, field in sources:
        for obj in qs.exclude(**{field: ""}).exclude(**{f"{field}__isnull": True}):
            yield getattr(obj, field)


def delete_account(user) -> int:
    """Hard-delete ``user`` and everything they own. Returns files removed."""
    removed = 0
    for field_file in list(_stored_files(user)):
        try:
            field_file.storage.delete(field_file.name)
            removed += 1
        except Exception:  # best-effort: never block account deletion on storage
            logger.warning("delete_account: could not delete %s", field_file.name, exc_info=True)
    with transaction.atomic():
        user.delete()
    return removed
