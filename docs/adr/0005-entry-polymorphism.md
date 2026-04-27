# ADR-0005: Entry polymorphism via direct FK to BaseEntry

- **Status:** accepted
- **Date:** 2026-04-27
- **Phase:** 2.1

## Context

The CV domain has a polymorphic entry hierarchy: `EducationEntry`,
`ExperienceEntry`, `PublicationEntry`, `BulletEntry`, `TextEntry`, and so on.
A `Section` is an ordered collection of these heterogeneous rows, and a `CV`
references a set of `Section`s through `CVSection`.

The current implementation, inherited from Phase 0, hangs entries off
`SectionEntry` through Django's `contenttypes` framework:

```python
class SectionEntry(models.Model):
    section = FK(Section, …)
    order = PositiveIntegerField()

    content_type = FK(ContentType, …)
    object_id = UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
```

Plus a project-wide `pre_delete` signal in `apps/sections/models.py` that
fires for every entry subtype to manually clean up dangling section entries.

This works, but every part of it earns a complaint:

1. **Generic foreign keys can't enforce referential integrity.** Postgres
   has no idea that `(content_type=education, object_id=…)` should be a real
   row in `entries_educationentry`. A delete that escapes the signal — bulk
   `.delete()` with `_raw_delete=True`, an `UPDATE` that flips `object_id`,
   a manual SQL operation — leaves dangling rows. The `pre_delete` signal is
   the only thing standing between us and a `content_object is None` bug at
   render time.

2. **Every read joins through `ContentType`.** `Section.serialize()` calls
   `entry.content_object.serialize()` for every row in the section. With a
   plain `FK(BaseEntry)` and `InheritanceManager.select_subclasses()`, the
   ORM can fetch all subclass rows in one query per section. Today it issues
   one extra query per entry to look up the content type table.

3. **The signal is global and load-order sensitive.** It connects 9 senders
   at module-import time. In tests we've already had to think about
   `dispatch_uid` collisions; in Phase 3+ when we add a render queue worker,
   we'll need to think about it again. Every signal is a distributed
   conditional we can't see in stack traces.

4. **Type safety is gone.** `entry.content_object` has type `Any`. Every
   call site has to `isinstance`-check or trust comments. With
   `entry.entry`, mypy + django-stubs give us a real `BaseEntry`.

The only thing the GFK gets us is the ability to point `SectionEntry` at
something that isn't an entry — and we never want that. Every value in the
relation is, by definition, an entry.

## Decision

Replace the GFK on `SectionEntry` with a direct FK to `BaseEntry`. Keep
multi-table inheritance via `model_utils.InheritanceManager` for the entry
hierarchy itself.

```python
# apps/entries/models.py — unchanged
class BaseEntry(models.Model):
    user = FK(settings.AUTH_USER_MODEL, …)
    alias = CharField(20)
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    objects = InheritanceManager()


class EducationEntry(BaseEntry):
    institution = CharField(100)
    …


# apps/sections/models.py — changed
class SectionEntry(models.Model):
    section = FK(Section, on_delete=CASCADE, related_name="section_entries")
    entry = FK(
        "entries.BaseEntry",
        on_delete=CASCADE,
        related_name="section_entries",
    )
    order = PositiveIntegerField()

    class Meta:
        ordering = ["order"]
```

Specifically:

- **`BaseEntry` stays a concrete model.** Django's MTI already gives us a
  `entries_baseentry` table that every subclass row is joined to. The FK
  points there. `Entry.objects.select_subclasses()` resolves the row to its
  most-specific subclass at read time — a single LEFT JOIN sweep that the
  ORM does for us.
- **`on_delete=CASCADE` replaces the signal.** When a `BaseEntry` row is
  deleted (which cascades from each subclass's CASCADE-up to its parent),
  Postgres deletes the matching `SectionEntry` rows. No signal, no
  ContentType, no module-import side effects.
- **`SectionEntry.entry` returns a typed `BaseEntry`.** Call sites that
  need the concrete subclass use the existing `InheritanceManager`:
  `Entry.objects.filter(pk=entry.pk).select_subclasses().first()`. Or — the
  more common case — `entry.serialize()` which is polymorphic on the
  subclass via Django's MTI.

The `pre_delete` signal block in `apps/sections/models.py`, the
`_ENTRY_MODELS` tuple, and the `_delete_dangling_section_entries` function
all get deleted.

## Migration plan

Phase 2 still has no real data, so the migration is a structural change
without a backfill. Concretely:

1. Generate a migration that:
   - Adds `SectionEntry.entry = FK(BaseEntry, …, null=True)`.
   - Backfills `entry_id = object_id` (which is already a UUID matching
     `BaseEntry.id` because every subclass shares its parent's PK in MTI).
   - Drops `content_type`, `object_id`.
   - Flips `entry` to `null=False`.
2. Delete the signal-connect block and the `_ENTRY_MODELS` tuple from
   `apps/sections/models.py`.
3. Update `Section.serialize()` and `SectionEntry.serialize()` to use
   `.entry` instead of `.content_object`.
4. Update `SectionManager.create_all_sections` to set `entry=` instead of
   `content_object=`.
5. Drop `django.contrib.contenttypes` imports.

Because dev/CI databases have no fixture data, the backfill is a safety
net — it would protect a real-data migration if we ever reuse this pattern.

## Consequences

### Positive

- **Database-enforced referential integrity.** A `SectionEntry` cannot
  point at a non-existent entry. Postgres rejects the row.
- **One JOIN, not two.** `Section.section_entries.select_related("entry")`
  in one shot. Subclass resolution via `select_subclasses()` is one
  additional LEFT JOIN sweep across the entry tables, not 9 separate
  queries.
- **Cascade is local and visible.** `on_delete=CASCADE` lives on the field
  declaration; anyone reading `SectionEntry` knows the lifecycle. No grep
  for `pre_delete.connect` to figure out what cleans up dangling rows.
- **Type-checkable.** `entry.entry: BaseEntry` is a real type that
  django-stubs/mypy understand. `content_object: Any` is gone.
- **Fewer moving parts.** No `contenttypes` framework dependency for this
  relation. (Django still uses contenttypes for permissions and the admin;
  we're not uninstalling the app, we're just not abusing it.)

### Negative

- **One-time migration risk.** If we ever reuse SectionEntry to point at a
  non-entry model — say, a future "section header" or "page break" type —
  we'd need to rethink the relation. We don't have such a use case; the
  domain is "ordered list of entries" by definition.
- **`select_subclasses()` materializes one extra LEFT JOIN per entry
  subclass.** With 9 subclasses, that's 9 LEFT JOINs in the generated SQL.
  Postgres handles that fine for collections in the hundreds; if the
  numbers ever got into the thousands per section we'd want to revisit.
  Today's design ceiling is ~50 entries per section, so this is a
  non-concern.

### Neutral

- The `BaseEntry` row count grows linearly with total entries (one parent
  row per subclass row). Storage cost is unchanged from the GFK design
  because `BaseEntry` already exists as the MTI parent.

## Alternatives considered

- **Keep the GFK, harden the signal.** Adds a `dispatch_uid` per
  send-time, audits the signal connections in tests. Solves the
  load-order issue but not the referential-integrity or query-count
  problems. The signal stays a global side effect.
- **Single-table inheritance (one big `Entry` table with a `kind`
  column and nullable per-kind fields).** Trades schema clarity for query
  simplicity. We'd lose constraint-level "education entries must have an
  institution" enforcement, and adding a new kind would mean migrating
  the whole table. Multi-table inheritance is the right shape for
  diverging field sets like ours.
- **`django-polymorphic` instead of `model_utils.InheritanceManager`.**
  More features (parent-class aware querysets, polymorphic admin),
  more magic. We use `select_subclasses()` in maybe a dozen places;
  the magic isn't worth the extra dependency.
- **Replace the GFK with a JSONField column on `SectionEntry` storing the
  entry payload directly.** Denormalizes hard. Means duplicate writes
  whenever an entry is edited. Loses the ability to "swap which entries
  are in this section" without rewriting all the JSON. Wrong shape.

## References

- [Django: Multi-table inheritance](https://docs.djangoproject.com/en/5.1/topics/db/models/#multi-table-inheritance)
- [django-model-utils: InheritanceManager](https://django-model-utils.readthedocs.io/en/latest/managers.html#inheritancemanager)
- [Django: GenericForeignKey caveats](https://docs.djangoproject.com/en/5.1/ref/contrib/contenttypes/#generic-relations)
