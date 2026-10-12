"""Real Help and Import pages (replacing the "coming soon" placeholders)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from cv.models import CV

pytestmark = pytest.mark.django_db


def test_help_explains_the_workflow_to_anyone(client):
    body = client.get(reverse("help")).content.decode()
    for phrase in (
        "Entries",
        "Sections",
        "CVs",
        "+ New CV",
        "+ Add section",
        "+ New entry",
        "One kind per section",
    ):
        assert phrase in body, phrase
    assert "coming soon" not in body.lower() and "isn't built yet" not in body


def test_help_links_resolve(client):
    body = client.get(reverse("help")).content.decode()
    for name in ("cv-list", "import", "profile", "api:schema"):
        assert f'href="{reverse(name)}"' in body, name


def test_import_page_for_anonymous_asks_to_log_in(client):
    body = client.get(reverse("import")).content.decode()
    assert "Log in to import" in body and 'type="file"' not in body
    assert f"next={reverse('import')}" in body


def test_import_page_form_posts_to_the_upload_endpoint(client, user):
    client.force_login(user)
    body = client.get(reverse("import")).content.decode()
    assert f'action="{reverse("cv-upload")}"' in body and 'enctype="multipart/form-data"' in body
    assert 'name="yaml_file"' in body


def test_import_page_end_to_end(client, user):
    client.force_login(user)
    yaml_text = b"cv:\n  name: Ada Lovelace\n  sections:\n    skills:\n      - label: Math\n        details: Analysis\n"
    resp = client.post(
        reverse("cv-upload"),
        {"yaml_file": SimpleUploadedFile("ada.yaml", yaml_text)},
        follow=True,
    )
    cv = CV.objects.get(user=user)
    assert resp.redirect_chain[-1][0] == reverse("cv-editor", args=[cv.id])


def test_nav_no_longer_links_the_templates_placeholder(client, user):
    for visitor in (client,):
        body = visitor.get(reverse("homepage")).content.decode()
        assert f'href="{reverse("templates")}"' not in body
        assert f'href="{reverse("help")}"' in body and f'href="{reverse("import")}"' in body
