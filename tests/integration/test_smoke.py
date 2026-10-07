"""Smoke tests.

Cheap, fast checks that catch catastrophic regressions: URL reversal,
public pages returning 200, the admin loading, migrations applying cleanly.

These are the first tests CI runs — if they fail, nothing else matters.
"""

from __future__ import annotations

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    [
        "homepage",
        "about",
        "help",
        "contact",
        "status",
        "templates",
        "import",
    ],
)
def test_public_stubs_render_200(client, name):
    """Every Phase 0 placeholder route should still return a friendly page."""
    url = reverse(name)
    resp = client.get(url)
    assert resp.status_code == 200


def test_admin_login_page(client):
    resp = client.get("/admin/login/")
    assert resp.status_code == 200


def test_admin_index_redirects_when_anon(client):
    resp = client.get("/admin/")
    # Django admin redirects anonymous users to the login page.
    assert resp.status_code in (302, 301)


def test_admin_index_authed(admin_client):
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Component kitchen-sink (Phase 4.2)
# ---------------------------------------------------------------------------
def test_components_kitchen_sink_renders(client, settings):
    """The /components/ route renders the Cotton component library.

    Catches broken component templates at test time: if a <c-...> tag
    references a missing or malformed file, the page raises
    TemplateDoesNotExist or TemplateSyntaxError instead of 200.
    """
    settings.DEBUG = True  # the view 404s outside DEBUG; flip per-test
    resp = client.get("/components/")
    assert resp.status_code == 200
    # Spot-check that a few components actually expanded.
    assert b"Primary" in resp.content  # button label
    assert b"font-display" in resp.content  # typography section


def test_components_kitchen_sink_hidden_outside_debug(client):
    """In test settings DEBUG is False -- the view 404s, the URL pattern stays."""
    resp = client.get("/components/")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# URL reversal — every named route must reverse without raising.
# ---------------------------------------------------------------------------
def _named_patterns(patterns, namespace=None):
    """Walk the URL tree, yielding fully-qualified pattern names.

    Namespaced routes (e.g. ``admin:auth_user_changelist``) need the prefix or
    ``reverse()`` won't find them. Namespaces can nest, so we accumulate them
    as we descend into ``URLResolver`` nodes.
    """
    for p in patterns:
        if isinstance(p, URLPattern) and p.name:
            yield f"{namespace}:{p.name}" if namespace else p.name
        elif isinstance(p, URLResolver):
            if p.namespace:
                sub_ns = f"{namespace}:{p.namespace}" if namespace else p.namespace
            else:
                sub_ns = namespace
            yield from _named_patterns(p.url_patterns, namespace=sub_ns)


def test_every_named_url_reverses():
    """Catches typos like `cvdesgin-list` at test time, not runtime."""
    resolver = get_resolver()
    failures = []
    for full_name in _named_patterns(resolver.url_patterns):
        try:
            reverse(full_name)
        except Exception as exc:  # pytest reports all failures together
            # Some routes require URL kwargs; skip those — they're validated per-view.
            if "NoReverseMatch" in exc.__class__.__name__ and "argument" in str(exc):
                continue
            failures.append((full_name, str(exc)))
    assert not failures, f"Unreversible URLs: {failures}"


@pytest.mark.parametrize(
    "name",
    ["cv-list", "cvinfo-list", "cvdesign-list", "cvlocale-list", "cvsettings-list"],
)
def test_cv_list_pages_render_for_logged_in_user(client, user, name):
    client.force_login(user)
    resp = client.get(reverse(name))
    assert resp.status_code == 200


def test_cv_detail_renders_for_owner(client, user, cv):
    client.force_login(cv.user)
    resp = client.get(reverse("cv-detail", args=[cv.id]))
    assert resp.status_code == 200
    assert b"Render PDF" in resp.content


# ---------------------------------------------------------------------------
# Template render coverage: every converted page, with real data where the
# page loops over it (list/detail), so a stale tag or bad URL kwarg fails here.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    [
        "cv-create",
        "cvinfo-create",
        "cvdesign-create",
        "cvlocale-create",
        "cvsettings-create",
        "section-create",
        "entry-create",
        "entry-list",
        "section-list",
    ],
)
def test_form_and_list_pages_render(client, user, name):
    client.force_login(user)
    assert client.get(reverse(name)).status_code == 200


def test_entry_create_step_two_renders(client, user):
    client.force_login(user)
    resp = client.get(reverse("entry-create"), {"entry_type": "education"})
    assert resp.status_code == 200
    assert b"cv-form" in resp.content


def test_entry_pages_render_with_data(client, user, education_entry, bullet_entry):
    client.force_login(user)
    assert client.get(reverse("entry-list")).status_code == 200
    for entry in (education_entry, bullet_entry):
        for name in ("entry-detail", "entry-edit"):
            assert client.get(reverse(name, kwargs={"entry_id": entry.id})).status_code == 200


def test_cv_pages_render_with_data(client, cv):
    client.force_login(cv.user)
    assert client.get(reverse("cv-list")).status_code == 200
    assert client.get(reverse("cv-edit", args=[cv.id])).status_code == 200


def test_section_pages_render_with_data(client, user, section):
    client.force_login(user)
    assert client.get(reverse("section-list")).status_code == 200
    assert client.get(reverse("section-detail", args=[section.id])).status_code == 200
    assert client.get(reverse("section-edit", args=[section.id])).status_code == 200


def test_cv_update_saves_fields_and_section_order(client, user, cv, other_user):
    from sections.models import CVSection
    from tests.factories import SectionFactory

    first, second = SectionFactory(user=user), SectionFactory(user=user)
    foreign = SectionFactory(user=other_user)
    client.force_login(user)

    order = ",".join(str(s.id) for s in (second, first, foreign))
    resp = client.post(
        reverse("cv-edit", args=[cv.id]),
        {"alias": "renamed", "section_order": order},
    )

    assert resp.status_code == 302
    cv.refresh_from_db()
    assert cv.alias == "renamed"
    rows = list(
        CVSection.objects.filter(cv=cv).order_by("order").values_list("section_id", "order")
    )
    # Order honoured; another user's section silently dropped.
    assert rows == [(second.id, 1), (first.id, 2)]


def test_cv_edit_is_owner_only(client, cv, other_user):
    client.force_login(other_user)
    assert client.get(reverse("cv-edit", args=[cv.id])).status_code == 404
