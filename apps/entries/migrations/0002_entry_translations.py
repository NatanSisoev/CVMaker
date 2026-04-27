"""
Phase 2.2 (ADR-0006): per-entry translations.

Adds two columns to ``entries.BaseEntry``:

  - ``canonical_language`` (CharField(2), default "en"): the language the
    canonical column values are written in.
  - ``translations`` (JSONField, default {}): per-language field overrides.

Both fields have safe defaults, so this migration is a no-op data-wise:
existing rows pick up ``canonical_language="en"`` and an empty bag.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("entries", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="baseentry",
            name="canonical_language",
            field=models.CharField(
                default="en",
                help_text=(
                    "ISO 639-1 code identifying the language the canonical "
                    "columns are written in."
                ),
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name="baseentry",
            name="translations",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Per-language field overrides keyed by ISO 639-1 code, "
                    'e.g. {"es": {"summary": "..."}, "fr": {"summary": "..."}}'
                ),
            ),
        ),
    ]
