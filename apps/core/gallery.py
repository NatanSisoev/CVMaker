"""Public Templates gallery: every CV style, previewed with a sample CV."""

from __future__ import annotations

from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

from cv.models import CVDesign

THEME_BLURBS = {
    "classic": "Clean and conventional. A safe default for most applications.",
    "sb2nov": "Compact and technical, popular for software roles.",
    "engineeringresumes": "Dense single-column layout in the r/EngineeringResumes style.",
    "engineeringclassic": "The classic look with engineering-resume spacing.",
    "moderncv": "Colourful header and a sidebar-free modern layout.",
}

SAMPLE_CV = {
    "cv": {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "location": "London, UK",
        "sections": {
            "Summary": [
                "Mathematician and writer who published the first algorithm for a machine."
            ],
            "Experience": [
                {
                    "company": "Analytical Engine Project",
                    "position": "Programmer",
                    "start_date": "1842-01",
                    "end_date": "1843-10",
                    "highlights": ["Wrote the Note G algorithm for Bernoulli numbers."],
                }
            ],
            "Education": [
                {
                    "institution": "Private tutoring",
                    "area": "Mathematics",
                    "degree": "BS",
                    "start_date": "1832-01",
                    "end_date": "1835-01",
                }
            ],
            "Skills": [{"label": "Languages", "details": "French, English, Mathematics"}],
        },
    }
}

CACHE_SECONDS = 60 * 60 * 24


def styles() -> list[dict]:
    return [
        {"value": value, "label": label, "blurb": THEME_BLURBS.get(value, "")}
        for value, label in CVDesign.THEME_CHOICES
        if value != "custom"
    ]


@require_GET
def gallery_view(request):
    return render(request, "gallery.html", {"styles": styles()})


@require_GET
@xframe_options_sameorigin
def sample_pdf_view(request, theme):
    from rendering.tasks import _render_payload_to_pdf

    if theme not in {s["value"] for s in styles()}:
        raise Http404("unknown style")
    key = f"gallery-sample-{theme}"
    pdf = cache.get(key)
    if pdf is None:
        pdf = _render_payload_to_pdf(SAMPLE_CV, theme)
        cache.set(key, pdf, CACHE_SECONDS)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="sample-{theme}.pdf"'
    return response
