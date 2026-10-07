"""End-to-end render through the real rendercv 2.x + Typst pipeline (no mocks)."""

from __future__ import annotations

import pytest

from cv.models import CVInfo
from cv.services import build_render_payload
from rendering import tasks as rendering_tasks
from sections.models import CVSection, SectionEntry
from tests.factories import (
    CVFactory,
    EducationEntryFactory,
    ExperienceEntryFactory,
    SectionFactory,
)


@pytest.fixture
def full_cv(db, user):
    info = CVInfo.objects.create(
        user=user, alias="me", name="Ada Lovelace", email="ada@example.com"
    )
    cv = CVFactory(user=user, info=info)
    # rendercv needs one entry type per section.
    for order, (title, entry) in enumerate(
        (
            (
                "Experience",
                ExperienceEntryFactory(
                    user=user, company="Analytical Engines", position="Programmer"
                ),
            ),
            ("Education", EducationEntryFactory(user=user, institution="Home", area="Mathematics")),
        ),
        1,
    ):
        section = SectionFactory(user=user, title=title)
        SectionEntry.objects.create(section=section, entry=entry, order=1)
        CVSection.objects.create(cv=cv, section=section, order=order)
    return cv


def test_real_pipeline_produces_a_pdf(full_cv):
    payload = build_render_payload(full_cv)
    pdf = rendering_tasks._render_payload_to_pdf(payload)
    assert pdf.startswith(b"%PDF")


def test_style_override_changes_output(full_cv):
    payload = build_render_payload(full_cv)
    classic = rendering_tasks._render_payload_to_pdf(payload, style="classic")
    moderncv = rendering_tasks._render_payload_to_pdf(payload, style="moderncv")
    assert classic.startswith(b"%PDF") and moderncv.startswith(b"%PDF")
    assert classic != moderncv


def test_cv_without_info_fails_readably(db, user):
    cv = CVFactory(user=user)
    with pytest.raises(rendering_tasks._RenderError, match="personal information"):
        rendering_tasks._render_payload_to_pdf(build_render_payload(cv))


def test_invalid_data_surfaces_validation_message(full_cv):
    payload = build_render_payload(full_cv)
    payload["cv"]["email"] = "not-an-email"
    with pytest.raises(rendering_tasks._RenderError, match="not valid"):
        rendering_tasks._render_payload_to_pdf(payload)


def test_worker_entry_point_stores_real_pdf(full_cv, monkeypatch):
    from rendering import services as rendering_services
    from rendering.models import RenderStatus
    from rendering.services import enqueue_render

    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda render: None)

    render = enqueue_render(full_cv)
    rendering_tasks.render_cv(render.id)

    render.refresh_from_db()
    assert render.status == RenderStatus.DONE, render.error
    with render.pdf_file.open("rb") as fh:
        assert fh.read(4) == b"%PDF"
