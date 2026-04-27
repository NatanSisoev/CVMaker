# ADR-0006: Per-entry translations via JSONField

- **Status:** accepted
- **Date:** 2026-04-27
- **Phase:** 2.2

## Context

The product's central promise is *write each experience once, render it in
the language a specific role wants*. A user writes their Master's thesis
entry in English; six months later they apply to a Spanish lab and want the
same entry, in Spanish, without retyping it. The translation belongs to the
**entry**, not the CV — one entry can appear in many CVs and inherit the
language each CV picked.

That means we need:

1. A storage location for translations keyed by language code, scoped to
   the entry.
2. A **canonical** language — the source the user wrote first, used as the
   fallback when a target language is missing.
3. A read path that resolves "give me this entry in language X" with a
   sensible fallback to canonical.
4. A write path that lets a user edit translations side-by-side per
   language tab in the entry form.

Constraints worth pinning down:

- Translatable fields **vary per entry subtype**. `EducationEntry` has
  `area`, `degree`, `summary`, `highlights`. `BulletEntry` has just
  `bullet`. The system needs to know which fields participate in
  translation per subtype.
- Translations are **sparse**. Most users will write in one language. A
  minority will translate one or two CVs into a second language. A few
  power users will maintain three or more.
- Reads are bounded — a CV's render path touches every entry in every
  section it includes, but that's tens of entries per render, not
  thousands.
- Writes are infrequent — translation editing happens in occasional bursts
  when a user prepares a new CV.

## Decision

Each `BaseEntry` carries:

```python
canonical_language = CharField(max_length=2, default="en")
translations       = JSONField(default=dict, blank=True)
```

`translations` is a dict keyed by ISO 639-1 code (`"es"`, `"fr"`, `"de"`).
Each value is a dict of translatable field names to string values.

```jsonc
{
  "es": {"summary": "Tesis sobre…", "highlights": "primer puesto; beca…"},
  "fr": {"summary": "Thèse sur…",   "highlights": "premier prix; bourse…"}
}
```

Each subclass declares its translatable fields:

```python
class EducationEntry(BaseEntry):
    TRANSLATABLE_FIELDS = ("area", "degree", "summary", "highlights")
    …

class BulletEntry(BaseEntry):
    TRANSLATABLE_FIELDS = ("bullet",)
    …
```

A `get_field()` helper on `BaseEntry` does the lookup with fallback:

```python
def get_field(self, name: str, language: str | None = None) -> str:
    """Return the value of `name`, translated to `language` if possible.

    Fallback rules:
      1. If `language` is None or matches `canonical_language`, return the
         canonical column value as-is.
      2. If `language` is in `translations` AND that bag has `name`, return
         it (even if empty).
      3. Otherwise, fall back to the canonical column value.
    """
```

`serialize(language=…)` is rewritten to use `get_field` for every
translatable column. Untranslatable columns (dates, URLs, structural
fields like `institution`) come straight off the row.

At render time the call chain is:

```
RenderingService.build_payload(cv)
  → for section in cv.sections:
      → for entry in section.entries:
          entry.serialize(language=cv.locale.language)
```

`CVLocale` already has a `language` field (Phase 0); Phase 2.2 wires it
through to the serializer.

## Why JSONField, not a separate translations table

The shape of the data is **entry-local**, **sparse**, and **rarely written
in batches across entries**. A relational translations table would mean:

- One JOIN per (entry, language) pair at render time.
- A separate model + admin + migration when adding a new translatable
  field. Today's `summary` change → tomorrow's schema migration.
- Synthetic surrogate keys with no inherent uniqueness — the natural key is
  `(entry_id, language, field_name)`, and we'd be carrying a redundant
  integer PK for every row.

JSONField gives us:

- Zero extra JOIN; the translations bag travels with the entry row.
- New translatable field → tuple change in `TRANSLATABLE_FIELDS`. No
  migration.
- Postgres has first-class JSONB indexing if a query ever needs it (Phase
  9-ish, "find all entries with a Spanish translation").
- Native dict access in Python; tests assert on real shapes.

The cost is loss of FK-level integrity checks ("did we accidentally store
a translation under `summarry` instead of `summary`?"). We mitigate this
with `clean()` / form-level validation that rejects unknown keys.

## Why not django-modeltranslation

`django-modeltranslation` and similar packages create one column per
language per translatable field at the schema level — `summary_en`,
`summary_es`, `summary_fr`. Concretely:

- **Schema bloat scales as O(languages × fields).** Adding French triples
  the column count of every entry table.
- **Adding a language is a migration.** Every user gets schema downtime
  for a feature only one of them is using.
- **Admin UX is okay but not great.** Inline tabs require third-party
  packages we'd need to vet anyway.
- **The user-base is unbounded in language.** We don't want to commit to a
  finite set of languages at schema time.

JSON keyed by ISO code gives us infinite languages with no schema cost.

## Form / admin UX (Phase 4 finalizes)

A minimum viable surface lands in Phase 2.2:

- The entry create/edit form gets a language selector. Picking a language
  shows that language's translation fields side-by-side with the canonical
  fields, populated from `translations[lang]` or blank.
- Submission writes the bag back into `translations`. Untranslatable
  fields write to the canonical columns as today.
- Admin: a custom `ModelForm` for each subtype that renders the
  translatable fields once per language (collapsed fieldsets) so an
  admin can audit translations without dropping into JSON.

Phase 4 (Tailwind + HTMX rewrite) replaces the static language switcher
with a tabbed editor that swaps fields without a page reload.

## Migration plan

`accounts.User.preferred_language` already exists as the source of truth
for "what language the user writes in." That's what we default
`canonical_language` to.

1. Generate a migration that adds `canonical_language` (default
   `User.preferred_language` at row creation, fallback `"en"`) and
   `translations = JSONField(default=dict)` to `BaseEntry`.
2. No backfill — every existing entry gets `canonical_language="en"` and
   `translations={}`. Dev DB has no real data, so this is a noop.
3. Update each subclass's `serialize()` to call `self.get_field(name,
   language=language)` for every name in `TRANSLATABLE_FIELDS`. Pass
   `language` through from `Section.serialize` and from `CVSection`.
4. `CVLocale.language` becomes the parameter that determines what a render
   looks like.

## Consequences

### Positive

- **One source of truth per entry.** "Where is the Spanish version of my
  thesis entry?" → `entry.translations["es"]`. Always.
- **Zero schema cost for new languages.** Adding French is a UI-only
  change; the data store accepts any 2-letter code.
- **Render-time fallback is automatic.** Missing translations don't crash
  rendering — they degrade to canonical, which is what users expect.
- **Each entry subtype declares its own translatable fields.** No global
  registry, no central enum to update when adding a new subtype.

### Negative

- **No DB-level constraint that translation keys match
  `TRANSLATABLE_FIELDS`.** A bad write at the ORM layer can store
  `translations["es"]["summarry"] = "…"` and that ghost key never
  surfaces. Mitigated by `BaseEntry.clean()` rejecting unknown keys, but
  it's a runtime check, not a schema check.
- **Postgres JSONB beats SQLite JSON.** SQLite stores it as text and
  loses indexing. Tests use SQLite, prod uses Postgres — fine, but worth
  knowing.
- **Querying "all entries with a Spanish translation" requires a JSONB
  containment query.** Phase 9 territory; not Phase 2's problem.

### Neutral

- The translations bag travels with every entry row even when empty
  (`{}`). Storage overhead is negligible (≈ 2 bytes per row).

## Alternatives considered

- **Per-language separate columns** (`summary_en`, `summary_es`, …).
  Schema bloat, migration per language, finite language set. Rejected.
- **Separate `Translation` model with FK to `BaseEntry`, language code,
  field name, value.** Tabular but joins per render. Rejected for read
  cost and migration overhead.
- **Translations bound to `CVSection` instead of `BaseEntry`.** Means
  translations don't follow the entry across CVs — the user has to
  re-translate the same thesis for every Spanish CV. Misses the
  point of write-once.
- **Free-form translation memory at the user level**, decoupled from
  entries. Useful as a Phase 3+ feature for assisted translation, but
  doesn't substitute for entry-level storage of finished translations.

## References

- [Django: JSONField](https://docs.djangoproject.com/en/5.1/ref/models/fields/#jsonfield)
- [Postgres: JSONB indexing](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)
- [django-modeltranslation](https://django-modeltranslation.readthedocs.io/) — alternative we considered.
- [ISO 639-1 language codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
