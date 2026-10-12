import pytest
from django.urls import reverse

from cv.models import CV
from sections.models import CVSection
from sections.services import attach_section_to_cv

pytestmark = pytest.mark.django_db


def test_duplicate_copies_cv_and_keeps_sections(client, user, cv, section):
    attach_section_to_cv(cv, section)
    client.force_login(user)
    resp = client.post(reverse("cv-duplicate", args=[cv.id]))
    copy = CV.objects.exclude(pk=cv.pk).get(user=user)
    assert resp.status_code == 302 and resp.url == reverse("cv-editor", args=[copy.id])
    assert copy.alias.endswith(" copy") and len(copy.alias) <= 20
    assert CVSection.objects.filter(cv=copy, section=section).exists()
    assert CV.objects.filter(pk=cv.pk).exists()


def test_duplicate_requires_post_ownership_and_login(client, user, other_user, cv):
    assert client.post(reverse("cv-duplicate", args=[cv.id])).status_code == 302  # to login
    client.force_login(other_user)
    assert client.post(reverse("cv-duplicate", args=[cv.id])).status_code == 404
    client.force_login(user)
    assert client.get(reverse("cv-duplicate", args=[cv.id])).status_code == 405
    assert CV.objects.count() == 1
