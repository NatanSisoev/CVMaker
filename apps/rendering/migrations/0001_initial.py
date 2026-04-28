"""Phase 3.1: initial migration for the rendering app.

Creates the ``Render`` table per the model in ``apps/rendering/models.py``.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cv", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Render",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "language",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "ISO 639-1 code; empty string means "
                            "'use the CV's CVLocale.language'."
                        ),
                        max_length=2,
                    ),
                ),
                (
                    "style",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Theme/style override; empty string means "
                            "'use the CV's CVDesign'."
                        ),
                        max_length=50,
                    ),
                ),
                (
                    "payload_hash",
                    models.CharField(
                        db_index=True,
                        help_text=(
                            "SHA-256 of the canonicalized render input. Cache key."
                        ),
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("done", "Done"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=10,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "pdf_file",
                    models.FileField(
                        blank=True,
                        help_text="The rendered PDF; populated when status == 'done'.",
                        null=True,
                        upload_to="renders/%Y/%m/",
                    ),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text=(
                            "Captured stderr/exception text when status == 'failed'."
                        ),
                    ),
                ),
                (
                    "cv",
                    models.ForeignKey(
                        help_text="The CV being rendered.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="renders",
                        to="cv.cv",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="renders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-requested_at"],
                "indexes": [
                    models.Index(
                        fields=["payload_hash", "status"],
                        name="rendering_r_payload_idx",
                    ),
                ],
            },
        ),
    ]
