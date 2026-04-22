from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from cv.views import HomePageView


def _placeholder(page_title, page_description=None):
    """Temporary stub view until a real page is built. Phase 6 replaces these."""
    return TemplateView.as_view(
        template_name="placeholder.html",
        extra_context={"page_title": page_title, "page_description": page_description},
    )


urlpatterns = [
    path("", HomePageView.as_view(), name="homepage"),

    path("admin/", admin.site.urls),
    path("cv/", include("cv.urls")),
    path("section/", include("sections.urls")),
    path("entry/", include("entries.urls")),

    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),

    # Placeholder routes — these are linked from the nav / footer but don't have
    # real content yet. See ROADMAP.md Phase 6 for when these get built.
    path("templates/", _placeholder("Templates",
        "A gallery of ready-made CV templates you can start from."), name="templates"),
    path("import/", _placeholder("Import",
        "Import from a YAML, PDF, or LinkedIn URL."), name="import"),
    path("help/", _placeholder("Help"), name="help"),
    path("contact/", _placeholder("Contact"), name="contact"),
    path("status/", _placeholder("Status"), name="status"),
    path("about/", _placeholder("About"), name="about"),
]

# Serve MEDIA in dev only. In production Whitenoise + an object store handle this.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
