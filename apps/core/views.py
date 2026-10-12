"""Cross-app views that don't belong to any single domain app."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from cv.models import CV
from entries.models import BaseEntry
from sections.models import Section

PER_GROUP = 5

# (label, url name) -- static actions offered by the palette.
_ACTIONS = (
    ("My CVs", "cv-list"),
    ("New CV", "cv-new"),
    ("New entry", "entry-create"),
    ("New section", "section-create"),
    ("All entries", "entry-list"),
    ("All sections", "section-list"),
    ("Settings", "profile"),
)


@login_required
@require_GET
def palette_view(request):
    """Command-palette results (HTMX fragment), scoped to the user's own data.

    An empty query lists every action plus the most recently edited CVs.
    """
    q = request.GET.get("q", "").strip()
    user = request.user
    groups = []

    actions = [
        {"label": label, "url": reverse(name)}
        for label, name in _ACTIONS
        if not q or q.lower() in label.lower()
    ]
    if actions:
        groups.append(("Actions", actions))

    cvs = CV.objects.filter(user=user).order_by("-modified_date")
    if q:
        cvs = cvs.filter(alias__icontains=q)
    cv_items = [
        {"label": cv.alias, "hint": "Open editor", "url": reverse("cv-editor", args=[cv.id])}
        for cv in cvs[:PER_GROUP]
    ]
    if cv_items:
        groups.append(("CVs", cv_items))

    if q:
        sections = Section.objects.filter(user=user, title__icontains=q)[:PER_GROUP]
        section_items = [
            {"label": s.title, "hint": s.alias, "url": reverse("section-detail", args=[s.id])}
            for s in sections
        ]
        if section_items:
            groups.append(("Sections", section_items))

        entries = (
            BaseEntry.objects.filter(user=user, alias__icontains=q)
            .select_subclasses()
            .order_by("alias")[:PER_GROUP]
        )
        entry_items = [
            {
                "label": e.alias,
                "hint": type(e).__name__.removesuffix("Entry"),
                "url": reverse("entry-detail", kwargs={"entry_id": e.id}),
            }
            for e in entries
        ]
        if entry_items:
            groups.append(("Entries", entry_items))

    return render(request, "core/_palette_results.html", {"groups": groups, "q": q})


def ratelimited(request, exception=None):
    """429 for django-ratelimit (``RATELIMIT_VIEW``).

    HTMX callers get a toast via ``HX-Trigger`` (HTMX doesn't swap 4xx bodies);
    API callers get JSON; everyone else gets a page.
    """
    message = "Too many requests. Please wait a minute and try again."
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": message}, status=429)
    response = render(request, "429.html", {"message": message}, status=429)
    if request.headers.get("HX-Request") == "true":
        response["HX-Trigger"] = json.dumps({"toast": {"message": message, "variant": "error"}})
    response["Retry-After"] = "60"
    return response
