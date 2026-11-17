import pytest
from django.urls import reverse

from cv.tailor import keywords, tailor_cv
from sections.services import append_entry_to_section, attach_section_to_cv
from tests.factories import BulletEntryFactory, CVFactory, SectionFactory

pytestmark = pytest.mark.django_db


def test_keywords_drop_stop_words_and_rank_by_frequency():
    words = keywords("We need Python and Django. Python, Docker; you will use the cloud.")
    assert words[0] == "python" and "django" in words and "docker" in words
    assert "the" not in words and "and" not in words and "will" not in words


@pytest.fixture
def tailored(user):
    cv = CVFactory(user=user)
    section = SectionFactory(user=user, title="Work")
    append_entry_to_section(
        section, BulletEntryFactory(user=user, alias="py", bullet="Built Django services in Python")
    )
    append_entry_to_section(
        section, BulletEntryFactory(user=user, alias="cook", bullet="Baked bread")
    )
    attach_section_to_cv(cv, section)
    return cv


def test_entries_are_ranked_and_gaps_reported(tailored):
    result = tailor_cv(tailored, "Looking for Python and Django plus Kubernetes")
    assert [r["alias"] for r in result["ranked"]] == ["py", "cook"]
    assert {"python", "django"} <= set(result["ranked"][0]["matched"])
    assert result["ranked"][1]["score"] == 0
    assert "kubernetes" in result["missing"]


def test_view_renders_fragment_for_owner_only(client, user, other_user, tailored):
    url = reverse("cv-tailor", args=[tailored.id])
    assert client.post(url, {"posting": "python"}).status_code == 302
    client.force_login(other_user)
    assert client.post(url, {"posting": "python"}).status_code == 404
    client.force_login(user)
    body = client.post(url, {"posting": "python django"}).content.decode()
    assert "py" in body and "no match - consider cutting" in body
    assert "Paste a posting first" in client.post(url, {"posting": " "}).content.decode()
    assert client.get(url).status_code == 405


def test_editor_has_the_tailor_card(client, user, tailored):
    client.force_login(user)
    body = client.get(reverse("cv-editor", args=[tailored.id])).content.decode()
    assert "Tailor to a job" in body


def test_apply_puts_best_matches_first(client, user, other_user, tailored):
    from sections.models import SectionEntry

    section = tailored.sections.get()
    # Make "cook" the first entry so the reorder has something to do.
    cook = section.section_entries.get(entry__alias="cook")
    py = section.section_entries.get(entry__alias="py")
    cook.order, py.order = 0, 1
    cook.save()
    py.save()
    url = reverse("cv-tailor-apply", args=[tailored.id])

    client.force_login(other_user)
    assert client.post(url, {"posting": "python django"}).status_code == 404

    client.force_login(user)
    resp = client.post(url, {"posting": "Python and Django"})
    assert resp.status_code == 302
    order = list(
        SectionEntry.objects.filter(section=section)
        .order_by("order")
        .values_list("entry__alias", flat=True)
    )
    assert order == ["py", "cook"]
