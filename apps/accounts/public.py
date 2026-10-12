"""Opt-in public profile pages: ``/@handle/`` renders one chosen CV as HTML."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import User

_HEADLINE_KEYS = ("position", "degree", "name", "title", "label", "company", "institution")
_SUB_KEYS = ("company", "institution", "area", "location", "details", "summary", "date")
_SKIP = {"highlights", "bullet", "authors", "doi", "url"}


def _text(value) -> str:
    return ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)


def present_entry(entry) -> dict:
    """Flatten any serialized rendercv entry into headline / sub / bullets."""
    if isinstance(entry, str):
        return {"headline": "", "sub": "", "bullets": [entry]}
    headline = next((_text(entry[k]) for k in _HEADLINE_KEYS if entry.get(k)), "")
    sub_parts = [_text(entry[k]) for k in _SUB_KEYS if entry.get(k) and _text(entry[k]) != headline]
    start, end = entry.get("start_date"), entry.get("end_date")
    if start:
        sub_parts.append(f"{start} - {end or 'present'}")
    bullets = [_text(b) for b in entry.get("highlights", [])]
    if entry.get("bullet"):
        bullets.append(_text(entry["bullet"]))
    if entry.get("authors"):
        sub_parts.append(_text(entry["authors"]))
    return {"headline": headline, "sub": " · ".join(sub_parts), "bullets": bullets}


@require_GET
def public_profile_view(request, handle):
    try:
        user = User.objects.select_related("public_cv").get(
            public_handle=handle.lower(), public_cv__isnull=False
        )
    except User.DoesNotExist as exc:
        raise Http404("No such profile") from exc
    data = user.public_cv.serialize()
    info = dict(data.get("cv") or {})
    sections = info.pop("sections", {}) or {}
    contact = []
    if user.public_show_contact:
        contact = [info[k] for k in ("email", "phone") if info.get(k)]
    context = {
        "profile_user": user,
        "name": info.get("name") or user.get_display_name(),
        "location": info.get("location", ""),
        "website": info.get("website", ""),
        "contact": contact,
        "sections": [
            {"title": title, "entries": [present_entry(e) for e in entries]}
            for title, entries in sections.items()
        ],
    }
    response = render(request, "accounts/public_profile.html", context)
    response["X-Robots-Tag"] = "index, follow"
    return response
