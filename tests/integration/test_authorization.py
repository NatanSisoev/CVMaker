"""Ownership / login boundaries on the CV app.

Regressions for holes found in the 2026-10-08 audit: CV delete had no login
or ownership check; CVInfo/Design/Locale/Settings updates could edit -- and,
through the user-assigning mixin, take over -- another user's row; their
create views and CV detail 500'd for anonymous users.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from cv.models import CV, CVDesign, CVInfo, CVLocale, CVSettings
from tests.factories import CVFactory

pytestmark = pytest.mark.django_db


def test_cv_delete_by_non_owner_is_404_and_keeps_the_cv(client, cv, other_user):
    client.force_login(other_user)
    resp = client.post(reverse("cv-delete", kwargs={"cv_id": cv.id}))
    assert resp.status_code == 404
    assert CV.objects.filter(pk=cv.pk).exists()


def test_cv_delete_by_anonymous_redirects_and_keeps_the_cv(client, cv):
    resp = client.post(reverse("cv-delete", kwargs={"cv_id": cv.id}))
    assert resp.status_code == 302 and "login" in resp.url
    assert CV.objects.filter(pk=cv.pk).exists()


def test_cv_delete_by_owner_works(client, cv):
    client.force_login(cv.user)
    resp = client.post(reverse("cv-delete", kwargs={"cv_id": cv.id}))
    assert resp.status_code == 302
    assert not CV.objects.filter(pk=cv.pk).exists()


def test_cv_detail_anonymous_redirects(client, cv):
    resp = client.get(reverse("cv-detail", args=[cv.id]))
    assert resp.status_code == 302 and "login" in resp.url


def _make(model, user):
    if model is CVInfo:
        return CVInfo.objects.create(user=user, alias="a", name="Owner")
    if model is CVDesign:
        return CVDesign.objects.create(user=user, alias="a", theme="classic")
    if model is CVLocale:
        return CVLocale.objects.create(user=user, alias="a", language="en")
    return CVSettings.objects.create(user=user, alias="a")


SUBMODELS = [
    (CVInfo, "cvinfo", "info_id"),
    (CVDesign, "cvdesign", "design_id"),
    (CVLocale, "cvlocale", "locale_id"),
    (CVSettings, "cvsettings", "settings_id"),
]


@pytest.mark.parametrize(("model", "prefix", "kwarg"), SUBMODELS)
def test_submodel_update_by_non_owner_is_404_and_ownership_unchanged(
    client, user, other_user, model, prefix, kwarg
):
    obj = _make(model, user)
    client.force_login(other_user)
    url = reverse(f"{prefix}-edit", kwargs={kwarg: obj.pk})

    assert client.get(url).status_code == 404
    assert client.post(url, {}).status_code == 404
    obj.refresh_from_db()
    assert obj.user == user


@pytest.mark.parametrize(("model", "prefix", "kwarg"), SUBMODELS)
def test_submodel_create_and_edit_require_login(client, user, model, prefix, kwarg):
    obj = _make(model, user)
    for url in (reverse(f"{prefix}-create"), reverse(f"{prefix}-edit", kwargs={kwarg: obj.pk})):
        resp = client.get(url)
        assert resp.status_code == 302 and "login" in resp.url, url


@pytest.mark.parametrize(("model", "prefix", "kwarg"), SUBMODELS)
def test_submodel_edit_by_owner_renders(client, user, model, prefix, kwarg):
    obj = _make(model, user)
    client.force_login(user)
    assert client.get(reverse(f"{prefix}-edit", kwargs={kwarg: obj.pk})).status_code == 200


def test_legacy_render_routes_are_gone(client, cv):
    from django.urls import NoReverseMatch

    for name in ("cv-download", "cv-preview"):
        with pytest.raises(NoReverseMatch):
            reverse(name, args=[cv.id])


def test_other_users_cv_not_listed(client, user, other_user):
    CVFactory(user=other_user, alias="theirs")
    client.force_login(user)
    assert b"theirs" not in client.get(reverse("cv-list")).content
