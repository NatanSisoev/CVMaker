"""Housekeeping: delete expired share links and old render history.

Run from cron / a scheduler, e.g. ``python manage.py prune_data --render-days 90``.
Keeps each CV's newest finished render regardless of age, and never removes a
render that still has a live share link.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils import timezone

from rendering.models import Render, RenderStatus, ShareLink


class Command(BaseCommand):
    help = "Delete expired/revoked share links and renders older than --render-days."

    def add_arguments(self, parser):
        parser.add_argument("--render-days", type=int, default=90)
        parser.add_argument("--link-grace-days", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        now = timezone.now()
        dry = opts["dry_run"]

        dead_links = ShareLink.objects.filter(
            expires_at__lt=now - timedelta(days=opts["link_grace_days"])
        ) | ShareLink.objects.filter(
            revoked=True, created_at__lt=now - timedelta(days=opts["link_grace_days"])
        )
        links = dead_links.count()

        newest = Render.objects.filter(
            cv=OuterRef("cv"), status=RenderStatus.DONE, requested_at__gt=OuterRef("requested_at")
        )
        live = ShareLink.objects.filter(render=OuterRef("pk"), revoked=False, expires_at__gt=now)
        old = (
            Render.objects.filter(requested_at__lt=now - timedelta(days=opts["render_days"]))
            .annotate(has_newer=Exists(newest), is_shared=Exists(live))
            .filter(has_newer=True, is_shared=False)
        )
        renders = old.count()

        if not dry:
            dead_links.delete()
            for render in old.iterator():
                if render.pdf_file:
                    render.pdf_file.delete(save=False)
                render.delete()
        verb = "Would delete" if dry else "Deleted"
        self.stdout.write(f"{verb} {links} share link(s) and {renders} render(s).")
