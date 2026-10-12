"""
Root URL configuration.

Apps mount their own urlpatterns under path prefixes. The handful of
``_placeholder`` routes exist because the nav + footer link to them; real
content arrives in Phase 6.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import Http404
from django.shortcuts import render
from django.urls import URLPattern, URLResolver, include, path
from django.views.generic import TemplateView

from accounts.public import public_profile_view
from core.gallery import gallery_view, sample_image_view, sample_pdf_view
from core.views import (
    contact_view,
    healthz,
    palette_view,
    readyz,
    robots_txt,
    sitemap_xml,
    status_view,
)
from cv.views import HomePageView


def _components_view(request):
    """Dev-only kitchen-sink for the Cotton component library.

    The URL is registered unconditionally so it's reachable from the
    test client under ``DEBUG=False``; the view itself 404s outside
    ``DEBUG`` so prod can't expose it. Phase 4.2 smoke-tests that this
    route returns 200 in dev so CI catches a broken component (the
    template would fail to render rather than 200).
    """
    if not settings.DEBUG:
        raise Http404("components kitchen-sink is dev-only")
    return render(request, "components.html")


def _placeholder(page_title: str, page_description: str | None = None):
    """Temporary stub view until a real page is built."""
    return TemplateView.as_view(
        template_name="placeholder.html",
        extra_context={"page_title": page_title, "page_description": page_description},
    )


urlpatterns: list[URLPattern | URLResolver] = [
    path("", HomePageView.as_view(), name="homepage"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls", namespace="api")),
    path("@<str:handle>/", public_profile_view, name="public-profile"),
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("palette/", palette_view, name="palette"),
    # Domain apps
    path("cv/", include("cv.urls")),
    path("section/", include("sections.urls")),
    path("entry/", include("entries.urls")),
    path("", include("rendering.urls", namespace="rendering")),
    # Auth (allauth replaces these in Phase 6)
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),  # login, signup, verify, reset, 2FA
    # Placeholder routes — linked from nav/footer, real content in Phase 6
    path("templates/", gallery_view, name="templates"),
    path("templates/<str:theme>/sample.png", sample_image_view, name="template-image"),
    path("templates/<str:theme>/sample.pdf", sample_pdf_view, name="template-sample"),
    path("import/", TemplateView.as_view(template_name="import.html"), name="import"),
    path("help/", TemplateView.as_view(template_name="help.html"), name="help"),
    path("contact/", contact_view, name="contact"),
    path("status/", status_view, name="status"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    # Cotton component kitchen-sink. View 404s outside DEBUG; URL stays
    # registered so tests can hit it under test settings.
    path("components/", _components_view, name="components"),
]

# Serve MEDIA in dev only; prod puts it on S3 (Phase 8).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug toolbar.
    try:
        import debug_toolbar

        urlpatterns.insert(0, path("__debug__/", include(debug_toolbar.urls)))
    except ImportError:
        pass
