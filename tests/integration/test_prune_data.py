from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from rendering.models import Render, RenderStatus, ShareLink
from tests.factories import CVFactory

pytestmark = pytest.mark.django_db


def _render(cv, days_old, status=RenderStatus.DONE):
    r = Render.objects.create(cv=cv, payload_hash=f"h{days_old}", status=status)
    Render.objects.filter(pk=r.pk).update(requested_at=timezone.now() - timedelta(days=days_old))
    return r


def test_prune_keeps_newest_and_shared_and_recent(capsys):
    cv = CVFactory()
    newest_old = _render(cv, 200)
    mid = _render(cv, 100)
    shared = _render(cv, 150)
    recent = _render(cv, 5)
    ShareLink.objects.create(render=shared, expires_at=timezone.now() + timedelta(days=1))

    call_command("prune_data", "--render-days", "90")

    remaining = set(Render.objects.values_list("pk", flat=True))
    assert remaining == {shared.pk, recent.pk}
    assert newest_old.pk not in remaining and mid.pk not in remaining


def test_prune_keeps_the_only_render_however_old():
    cv = CVFactory()
    only = _render(cv, 400)
    call_command("prune_data")
    assert Render.objects.filter(pk=only.pk).exists()


def test_prune_removes_long_dead_links_and_dry_run_changes_nothing(capsys):
    cv = CVFactory()
    r = _render(cv, 1)
    ShareLink.objects.create(render=r, expires_at=timezone.now() - timedelta(days=60))
    keep = ShareLink.objects.create(render=r, expires_at=timezone.now() - timedelta(days=2))
    call_command("prune_data", "--dry-run")
    assert ShareLink.objects.count() == 2 and "Would delete 1" in capsys.readouterr().out
    call_command("prune_data")
    assert list(ShareLink.objects.all()) == [keep]
