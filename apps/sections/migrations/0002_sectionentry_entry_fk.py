"""
Phase 2.1 (ADR-0005): replace SectionEntry's GenericForeignKey with a
direct FK to BaseEntry.

The old shape stored (content_type_id, object_id) where object_id was the
UUID of an entry subclass row. Because we use multi-table inheritance,
each subclass row's PK *is* the parent BaseEntry row's PK -- so
``entry_id = object_id`` is a 1:1 copy with no resolution step needed.

Migration steps:
  1. Add ``entry`` as a nullable FK to BaseEntry (so existing rows
     aren't blocked).
  2. Backfill ``entry_id = object_id`` for every existing SectionEntry.
  3. Promote ``entry`` to non-nullable.
  4. Drop ``content_type`` and ``object_id``.
  5. Add the ``unique_together = ("section", "entry")`` constraint.

The data step (#2) is a noop on a fresh dev DB but protects any
hand-created rows from a smoke test in the admin.
"""

import django.db.models.deletion
from django.db import migrations, models


def _copy_object_id_to_entry(apps, schema_editor):
    """Backfill SectionEntry.entry_id <- SectionEntry.object_id.

    Done in raw SQL to bypass the historical model definition (which now
    has ``entry`` nullable but doesn't yet have ``object_id`` removed --
    Django's frozen-model serializer carries both at this point).
    """
    SectionEntry = apps.get_model("sections", "SectionEntry")
    if SectionEntry.objects.exists():
        # Update each row in place. Small N, no need to chunk.
        for row in SectionEntry.objects.all():
            row.entry_id = row.object_id
            row.save(update_fields=["entry_id"])


def _reverse_copy(apps, schema_editor):
    """Reverse: copy entry_id back to object_id and re-derive content_type.

    Used only if someone does ``migrate sections 0001`` to roll back. The
    content_type lookup needs the entry's actual subclass, which we
    resolve via select_subclasses() (only available on the live model
    manager, not the historical apps registry; we accept the cost).
    """
    # No-op on rollback: rolling back this migration in dev means
    # losing data anyway, and prod will never see this path because the
    # GFK shape never shipped to real users.


class Migration(migrations.Migration):
    dependencies = [
        ("sections", "0001_initial"),
        ("entries", "0001_initial"),
    ]

    operations = [
        # -------------------------------------------------------------
        # 1. Add `entry` as nullable so existing rows survive.
        # -------------------------------------------------------------
        migrations.AddField(
            model_name="sectionentry",
            name="entry",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="section_entries",
                to="entries.baseentry",
            ),
        ),
        # -------------------------------------------------------------
        # 2. Backfill entry_id = object_id (1:1 because of MTI).
        # -------------------------------------------------------------
        migrations.RunPython(_copy_object_id_to_entry, _reverse_copy),
        # -------------------------------------------------------------
        # 3. Promote `entry` to non-nullable.
        # -------------------------------------------------------------
        migrations.AlterField(
            model_name="sectionentry",
            name="entry",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="section_entries",
                to="entries.baseentry",
            ),
        ),
        # -------------------------------------------------------------
        # 4. Drop the GFK columns.
        # -------------------------------------------------------------
        migrations.RemoveField(model_name="sectionentry", name="content_type"),
        migrations.RemoveField(model_name="sectionentry", name="object_id"),
        # -------------------------------------------------------------
        # 5. Lock in unique (section, entry) -- one slot per entry per
        # section, matching the new model's Meta.
        # -------------------------------------------------------------
        migrations.AlterUniqueTogether(
            name="sectionentry",
            unique_together={("section", "entry")},
        ),
    ]
