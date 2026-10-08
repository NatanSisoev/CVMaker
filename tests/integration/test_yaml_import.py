"""Dashboard *Import YAML* (``cv-upload``) on rendercv 2.x."""

from __future__ import annotations

import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from cv.importer import CVImportError, import_cv_from_yaml
from cv.models import CV
from entries.models import BaseEntry
from sections.models import Section

pytestmark = pytest.mark.django_db

GOOD_YAML = """\
cv:
  name: Ada Lovelace
  location: London
  email: ada@example.com
  phone: +44 20 7946 0958
  website: https://example.com/
  social_networks:
    - network: GitHub
      username: ada
  sections:
    experience:
      - company: Analytical Engines Ltd
        position: Programmer
        location: London
        start_date: 1842-09
        end_date: present
        highlights:
          - Wrote the first published algorithm
          - Predicted general-purpose computing
    education:
      - institution: Home schooling
        area: Mathematics
        degree: BS
        start_date: 1830
        end_date: 1835
    publications:
      - title: Notes on the Analytical Engine
        authors:
          - Ada Lovelace
          - Charles Babbage
        journal: Taylor's Scientific Memoirs
        date: 1843-10-01
    skills:
      - label: Languages
        details: English, French
    about:
      - A short paragraph of free text.
design:
  theme: moderncv
"""


def _entries(section_title):
    section = Section.objects.get(title=section_title)
    return list(
        BaseEntry.objects.filter(section_entries__section=section)
        .select_subclasses()
        .order_by("section_entries__order")
    )


def test_service_imports_every_entry_kind(user):
    cv = import_cv_from_yaml(user, GOOD_YAML, "My CV")

    assert cv.user == user and cv.alias == "my-cv"
    assert cv.info.name == "Ada Lovelace" and cv.info.email == "ada@example.com"
    assert cv.info.social_networks == {"GitHub": "ada"}
    assert cv.design.theme == "moderncv"
    assert list(cv.sections.order_by("cvsection__order").values_list("title", flat=True)) == [
        "Experience",
        "Education",
        "Publications",
        "Skills",
        "About",
    ]

    (job,) = _entries("Experience")
    assert type(job).__name__ == "ExperienceEntry"
    assert job.start_date == datetime.date(1842, 9, 1)
    assert job.end_date is None  # "present"
    assert job.highlights == (
        "Wrote the first published algorithm; Predicted general-purpose computing"
    )

    (school,) = _entries("Education")
    assert school.start_date == datetime.date(1830, 1, 1)

    (paper,) = _entries("Publications")
    assert paper.authors == "Ada Lovelace, Charles Babbage"
    assert paper.date == datetime.date(1843, 10, 1)

    (skill,) = _entries("Skills")
    assert (type(skill).__name__, skill.label) == ("OneLineEntry", "Languages")

    (about,) = _entries("About")
    assert (type(about).__name__, about.text) == ("TextEntry", "A short paragraph of free text.")


def test_imported_cv_renders_a_real_pdf(user):
    from cv.services import build_render_payload
    from rendering import tasks

    cv = import_cv_from_yaml(user, GOOD_YAML, "roundtrip")
    pdf = tasks._render_payload_to_pdf(build_render_payload(cv))
    assert pdf.startswith(b"%PDF")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty"),
        ("cv: [unclosed", "rendercv"),
        ("cv:\n  name: A\n  email: not-an-email\n", "not a valid rendercv CV"),
    ],
)
def test_service_rejects_bad_input_and_saves_nothing(user, text, message):
    with pytest.raises(CVImportError, match=message):
        import_cv_from_yaml(user, text, "bad")
    assert not CV.objects.exists()
    assert not BaseEntry.objects.exists()


def test_value_too_long_for_a_column_is_readable_and_atomic(user):
    long_yaml = GOOD_YAML.replace("degree: BS", "degree: " + "B" * 300)
    with pytest.raises(CVImportError, match="Could not import 'Education' entry 1: degree"):
        import_cv_from_yaml(user, long_yaml, "too-long")
    assert not CV.objects.exists() and not Section.objects.exists()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------
def _upload(client, content: bytes, name="cv.yaml"):
    return client.post(
        reverse("cv-upload"),
        {"yaml_file": SimpleUploadedFile(name, content, content_type="application/x-yaml")},
        follow=True,
    )


def test_upload_opens_the_editor_with_a_success_toast(client, user):
    client.force_login(user)
    resp = _upload(client, GOOD_YAML.encode(), "ada.yaml")

    cv = CV.objects.get(user=user)
    assert resp.redirect_chain[-1][0] == reverse("cv-editor", args=[cv.id])
    assert b"Imported ada." in resp.content


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"cv:\n  email: nope\n", b"not a valid rendercv CV"),
        (b"\xff\xfe\x00bad", b"isn&#x27;t UTF-8"),
        (b"cv: {}\n" + b"#" * (600 * 1024), b"too large"),
    ],
    ids=["invalid", "not-utf8", "too-large"],  # keep the 600 KB payload out of the test id
)
def test_upload_errors_come_back_as_a_toast_on_the_dashboard(client, user, content, message):
    client.force_login(user)
    resp = _upload(client, content)
    assert resp.redirect_chain[-1][0] == reverse("cv-list")
    assert message in resp.content
    assert not CV.objects.exists()


def test_upload_without_a_file(client, user):
    client.force_login(user)
    resp = client.post(reverse("cv-upload"), follow=True)
    assert b"Choose a rendercv YAML file" in resp.content


def test_upload_requires_login(client):
    resp = client.post(reverse("cv-upload"))
    assert resp.status_code == 302 and "login" in resp.url
