import pytest
from django.urls import reverse

from cv.models import CV, LimitExceeded
from tests.factories import CVFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_unlimited_by_default(user):
    for _ in range(4):
        CVFactory(user=user)
    assert CV.objects.filter(user=user).count() == 4


def test_cap_applies_per_user_and_only_to_new_cvs(settings, user):
    settings.MAX_CVS_PER_USER = 2
    first, _ = CVFactory(user=user), CVFactory(user=user)
    with pytest.raises(LimitExceeded):
        CVFactory(user=user)
    CVFactory(user=UserFactory())  # someone else is unaffected
    first.alias = "renamed"
    first.save()  # editing at the cap still works


def test_quick_create_at_cap_flashes_and_redirects(client, settings, user):
    settings.MAX_CVS_PER_USER = 1
    CVFactory(user=user)
    client.force_login(user)
    resp = client.post(reverse("cv-new"), {"alias": "Another"}, follow=True)
    assert resp.redirect_chain[-1][0] == reverse("cv-list")
    assert "reached the limit of 1 CV" in resp.content.decode()
    assert CV.objects.filter(user=user).count() == 1


def test_duplicate_at_cap_is_refused(client, settings, user):
    cv = CVFactory(user=user)
    settings.MAX_CVS_PER_USER = 1
    client.force_login(user)
    client.post(reverse("cv-duplicate", args=[cv.id]))
    assert CV.objects.filter(user=user).count() == 1
