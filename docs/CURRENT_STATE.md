# CVMaker — Current State Audit

_Snapshot taken 2026-04-21. Intended as a one-shot audit; it will not be kept in sync with reality. Once Phase 1 lands, delete this file. Until then, it's the shared memory between sessions about what we're starting from._

## What exists today

A Django 5.1 project that composes CVs from reusable, per-user building blocks and renders them to PDF through `rendercv` (which shells out to Typst).

**Domain model.** `User → CV → (CVInfo, CVDesign, CVLocale, CVSettings, Section[])`. A `Section` is an ordered collection of polymorphic `Entry` objects (Education, Experience, Publication, Normal, OneLine, Bullet, Numbered, ReversedNumbered, Text) wired up via a `SectionEntry` through-table that uses `ContentType` + `GenericForeignKey`. CVs are built by mixing and matching these blocks — this is the core idea of the product and it is fundamentally sound.

**Apps.** `accounts`, `cv`, `sections`, `entries`, plus the `cvmaker` project config. Templates live per-app and at the project root (`templates/base.html`, `templates/homepage.html`).

**Rendering.** `cv.views.download_cv` calls `rendercv.renderer.create_a_typst_file_and_copy_theme_files` then `render_a_pdf_from_typst` and streams the PDF back. Synchronous, in the request thread.

**YAML upload.** `CVUploadView` accepts a `rendercv` YAML file, validates it through `rendercv.data`, and materializes a full CV + sections + entries. Partially wired (the `CVDesign` branch is commented out and falls back to "first design in the table" — a bug).

**UI.** Bootstrap 5 via crispy-forms and widget-tweaks; a single hero homepage and per-model list/detail/form/delete templates.

**Auth.** `django.contrib.auth` with a `UserCreationForm`-based signup view. No email verification, no password reset UI, no social.

**DB.** PostgreSQL, hardcoded default credentials.

**Deployment scaffolding.** `gunicorn`, `whitenoise`, `dj-database-url` are all installed but nothing is wired up — no Dockerfile, no Procfile, no `ALLOWED_HOSTS`, no `SECURE_*` settings.

## What's broken or actively unsafe

These are the things that would bite us the moment we tried to deploy.

1. **`requirements.txt` is UTF-16 encoded.** It was saved from a Windows tool and `pip install -r` will fail on Linux/macOS. The whole file needs to be rewritten as UTF-8 and, ideally, replaced by `pyproject.toml` + a lockfile.
2. **Secrets are committed to source.** `SECRET_KEY` is hardcoded (`"django-insecure-…"`), `DB_PASSWORD` has a real-looking default. First commit of Phase 1 rotates these and moves everything to env.
3. **`user=…, default=1`** on `CV.user`. This is a booby trap: if user 1 doesn't exist, or if an unauthenticated code path ever creates a CV, it silently attaches to the admin. Must be removed.
4. **Settings are for dev only.** `DEBUG=True` default, empty `ALLOWED_HOSTS`, `EmailBackend` is console, no `SECURE_PROXY_SSL_HEADER`, no `CSRF_TRUSTED_ORIGINS`, no `SESSION_COOKIE_SECURE`.
5. **Broad `pre_delete` signal.** `sections/models.py` registers `delete_section_entries_for_deleted_entry` with no `sender=` — it runs for *every* model delete in the project, does a `ContentType` lookup, and a DELETE query. A denial-of-service vector against admin workflows.
6. **`CVInfo.save()` raises `ValidationError`.** Validation belongs in `clean()` / a form, not `save()`. Currently a bad `social_networks` value crashes an atomic write.
7. **Duplicate view logic.** `CVUpdateView` implements `get_context_data`, `post`, `form_valid`, `forms_valid`, and `forms_invalid` — three overlapping mechanisms doing the same thing, with stray `self.object.sections.clear()` calls that run twice. The update path is the riskiest file in the repo.
8. **No tests.** `tests.py` files are auto-generated stubs; zero coverage. This is non-negotiable before we refactor.
9. **PDF rendering runs in the request.** Typst compilation on a cold path can take several seconds; if a user triggers two downloads, gunicorn workers block. Must move to a task queue.
10. **Media files land on local disk.** `photo` uploads write to `BASE_DIR/media/` — doesn't survive a container restart, won't work on ephemeral PaaS filesystems.
11. **No i18n mechanism at the domain level.** The schema assumes one copy of each entry per user. The product vision is "same entry, many languages, pick at render time." This is the single biggest data-model gap.
12. **`typst`** the PyPI package is pinned, but `rendercv` itself vendors/drives typst via subprocess. The `typst` Python binding isn't actually used. Dead dep.
13. **`pyinstaller`** is pinned in requirements. Leftover from trying to package as a desktop app. Drop it.
14. **`CVSettingsDelete.success_url`** points to `"cv/cvsettings-list"` — that's a URL path, not a URL name. Crashes on delete.
15. **Dead URL handlers.** `cvmaker/urls.py` has five `path('…', lambda: None)` placeholders for templates/import/help/contact/status/about. Django will resolve them and then crash on request.
16. **`pk_url_kwarg = 'info_id'` on `CVInfoListView`.** ListView doesn't use pk kwargs — harmless but shows the pattern was copied without reading.
17. **`get_entry_model` forgets to `raise`** on the default case — a bad entry type silently returns `None`.
18. **`urls.py` uses `from .views import *`.** Masks name collisions.
19. **`.gitignore` is UTF-16**, same as `requirements.txt`.
20. **`cvmaker.tex`** (a TikZ explainer) has three trailing `];` typos in the `\draw` commands; it still compiles because of tolerant parsers, but it's a smell.

## What's good and should be preserved

- **The conceptual model**: reusable Info/Design/Locale/Settings + per-user library of Sections and Entries. This is genuinely the right abstraction for a CV builder and maps cleanly to the rendercv data model.
- **UUIDs as primary keys** on all user-owned objects. Keeps share links opaque and safe.
- **rendercv as the render engine.** Solid Pydantic-validated data model, five good themes out of the box, PDF-through-Typst is fast. We'll isolate it behind a job queue rather than replace it.
- **Per-user querysets** in forms. Tenant isolation is already the default pattern.
- **`alias`** per object. Lets users keep multiple variants ("default", "academic", "short") of each building block — this pattern is exactly what the "CV at the click of a button" vision needs.

## Files to delete on sight in Phase 1

`auxil/`, `out/`, `.idea/`, `desktop.ini`, `cvmaker.tex` (move to `docs/diagrams/` if kept), the `typst` and `pyinstaller` deps, every `__pycache__` committed to git.

## Next step

Read [`ROADMAP.md`](./ROADMAP.md) and [`DESIGN.md`](./DESIGN.md). Phase 1 is the first thing to execute in the next session.
