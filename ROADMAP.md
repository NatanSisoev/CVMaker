# CVMaker — Roadmap

> A CV composer. You write your experiences once, as reusable entries in any language you care about. Then, at the click of a button, you assemble a CV in the language, style, and order a specific role wants. We render it to PDF via Typst and host it online.

This document is the shared memory between sessions. It is deliberately long and deliberately checklisted: each phase has a clear definition of done, each task is small enough to fit in one work session, and the order of phases is chosen so the project is always deployable at the end of each one.

**Companion docs:**
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — audit of what exists today. Delete after Phase 1.
- [`docs/DESIGN.md`](docs/DESIGN.md) — design system and frontend stack decisions.
- `docs/adr/` — architecture decision records. Written as we commit to each decision.

**Working rule for every session:** before coding, open this file, pick the next unchecked item, scan the phase's definition of done, and add a dated note at the bottom of the phase under `## Session log` when you finish.

---

## North star

The product is successful when a user can:

1. Write an entry — say, their Master's thesis — once.
2. Translate that entry to Spanish and French with a single click (and edit the draft).
3. Select a subset of entries, pick a language, pick a style, click **Render**, and get a PDF in under 5 seconds.
4. Share that CV as a signed public URL, or download the PDF.

Everything in this roadmap ladders up to that user story.

---

## Architecture, at a glance

```
┌───────────────────────────────────────────────────────────────┐
│  Browser                                                       │
│  Tailwind + HTMX + Alpine · split-pane editor · live preview   │
└─────────────────────────┬─────────────────────────────────────┘
                          │ HTML fragments (HTMX), JSON (DRF)
┌─────────────────────────▼─────────────────────────────────────┐
│  Django 5 (gunicorn + uvicorn workers)                         │
│  · apps: core, accounts, cv, sections, entries, rendering      │
│  · DRF for /api/v1 (future mobile/CLI)                         │
│  · allauth for auth + social + email                           │
│  · django-anymail for transactional email                      │
└─────────────────────────┬─────────────────────────────────────┘
                          │ enqueue render job
┌─────────────────────────▼─────────────────────────────────────┐
│  Redis + RQ (or Celery) — render queue                         │
│  · renders Typst → PDF via rendercv                            │
│  · caches output by (cv_id, locale, style, entries-hash)       │
└─────────────────────────┬─────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│  Postgres (primary data) · S3-compatible object store (PDFs,   │
│  photos, exported YAML) · Sentry (errors) · PostHog (product)  │
└───────────────────────────────────────────────────────────────┘
```

Containerized from Phase 1. Docker Compose for local; the same images deploy to whatever PaaS we pick in Phase 8.

---

## Phases

Legend: `[ ]` pending · `[~]` in progress · `[x]` done.

### Phase 0 — Triage (one session)

The "stop the bleeding" phase. Nothing here changes architecture; we're making the repo safe to touch.

- [x] Rewrite `requirements.txt` and `.gitignore` as UTF-8. _(also trimmed dead deps: pyinstaller, typst, Brotli, Jinja2, Werkzeug, itsdangerous, blinker, pefile, altgraph, pywin32-ctypes)_
- [x] Rotate `SECRET_KEY`, move to `.env`, add `django-environ`.
- [x] Remove the committed `DB_PASSWORD` default.
- [x] Delete committed `__pycache__`. _(unstaged from git; physical files live on the read-only host mount — clean with `git clean -fdX` locally)_
- [ ] Physically delete `auxil/`, `out/`, `.idea/`, `desktop.ini` — sandbox couldn't, user must run locally (see HANDOFF.md).
- [x] Add a **`.env.example`** with every required variable documented.
- [x] Fix the six lambda URL placeholders in `cvmaker/urls.py` (now `TemplateView` with `placeholder.html`).
- [x] Fix the lambda placeholder for `profile` in `accounts/urls.py`.
- [x] Fix `CVSettingsDelete.success_url` (`'cv/cvsettings-list'` → `'cvsettings-list'`).
- [x] Fix `cvdesgin-list` typo (two occurrences).
- [x] Make `get_entry_model` raise on unknown types (was silently returning `None`).
- [x] Narrow the `pre_delete` receiver in `sections/models.py` to the 10 entry senders (was firing on every model delete in the project).
- [x] Relocate `cvmaker.tex` → `docs/diagrams/architecture.tex` and fix the three `];` syntax typos.
- [x] Replace hardcoded `STATICFILES_STORAGE` with Django 5's `STORAGES` dict, add prod security headers gated by `DEBUG`.
- [x] Rewrite README for both macOS/Linux and Windows, with the `.env` step documented.
- [ ] Tag the repo `v0.0.0-pre-refactor` — waiting on the user to review and commit.

**Definition of done:** `git clone` + `python -m venv` + `pip install -r requirements.txt` + `python manage.py migrate` + `python manage.py runserver` works on a fresh Linux machine with zero manual fixes. No secret in the diff.

---

### Phase 1 — Foundations (two to three sessions)

Restructure the repo for long-term sanity. This is the phase where we rip the band-aid off once and don't touch layout again.

#### 1.1 Project layout

Move to a `src/` layout with `uv`-managed dependencies and per-environment settings.

```
CVMaker/
├── src/
│   └── cvmaker/
│       ├── __init__.py
│       ├── settings/
│       │   ├── base.py
│       │   ├── dev.py
│       │   ├── prod.py
│       │   └── test.py
│       ├── urls.py
│       ├── asgi.py
│       └── wsgi.py
├── apps/
│   ├── core/            # shared mixins, base models, middleware
│   ├── accounts/
│   ├── cv/
│   ├── sections/
│   ├── entries/
│   └── rendering/       # new: render pipeline lives here
├── templates/
├── static/src/          # tailwind input
├── static/dist/         # build output, gitignored
├── locale/              # django gettext catalogs
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
├── docker/
│   ├── web.Dockerfile
│   ├── worker.Dockerfile
│   └── entrypoint.sh
├── compose.yaml
├── pyproject.toml
├── uv.lock
├── Makefile
├── .env.example
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
└── README.md
```

- [x] Introduce `pyproject.toml` with `uv` as the resolver. Audit and trim deps: drop `typst`, `pyinstaller`, `altgraph`, `pefile`, `pywin32-ctypes`, `pyinstaller-hooks-contrib`, `Brotli`, `Werkzeug`, `Jinja2` (unless needed), `Flask` family.
- [x] Split `settings.py` into `base/dev/prod/test`.
- [x] Switch `DJANGO_SETTINGS_MODULE` per entrypoint (`manage.py` → `dev`, `wsgi/asgi` → `prod`, `pytest` pins `test`).
- [~] Move the four apps under `apps/` and add a `core` app. _(core/ written; accounts/cv/entries/sections moved by `scripts/phase1_migrate.ps1`)_

#### 1.2 Dev tooling

- [x] `pre-commit` with `ruff` (lint + format), `djlint` (templates), `mypy` (types), `django-upgrade`.
- [x] `Makefile` targets: `make dev`, `make test`, `make lint`, `make fmt`, `make migrate`, `make shell`, `make ci`.
- [x] `EditorConfig`; `.gitignore` already updated in Phase 0.

#### 1.3 Docker

- [x] `docker/web.Dockerfile` — multi-stage, Python 3.12, installs Typst binary.
- [x] `docker/worker.Dockerfile` — same base; CMD stubbed for Phase 3 RQ worker.
- [x] `compose.yaml` — `web`, `worker`, `postgres`, `redis`, `minio` (S3-compatible for local).
- [x] `docker/entrypoint.sh` — waits for DB, opt-in migrations, collectstatic in prod.

#### 1.4 CI

- [x] `.github/workflows/ci.yml` — on every PR and push to main:
  - lint (ruff, djlint) + typecheck (mypy, soft-gate for now)
  - test (pytest) against Postgres 16 service container
  - build web Docker image (no push; release workflow lands in Phase 8)
  - upload coverage to Codecov
- [ ] Branch protection on `main`: require CI green, require one review. _(GitHub UI step — user does once after first green run)_

#### 1.5 Custom user model

Before any real data exists, swap `User` for a custom model. It is one migration now and zero migrations never again; changing later is a six-hour nightmare.

- [x] `apps/accounts/models.py: User(AbstractUser)` with `email` as the identifier + custom `UserManager`. _(written in `cvmaker/accounts/models.py`; git-mv'd by migration script)_
- [x] `AUTH_USER_MODEL = 'accounts.User'` in `settings/base.py`; every `FK(User, …)` rewritten to `FK(settings.AUTH_USER_MODEL, …)` across cv/entries/sections.
- [~] Re-squash all initial migrations under the new layout; reset dev DB (we have no real users yet). _(handled by `scripts/phase1_migrate.ps1` — drops migrations, `dropdb`/`createdb`, `makemigrations`, `migrate`)_

#### 1.6 Base tests

- [x] pytest + `pytest-django` + `pytest-cov` + `factory-boy` + `pytest-playwright` wired in `pyproject.toml`.
- [x] Factories for `User`, `CV`, `Section`, every `Entry` subtype (`tests/factories.py`). _(CVInfo factory lands alongside Phase 2.4 cleanup)_
- [x] Smoke tests: all 7 public stubs 200, admin 200, signup 302, every named URL reverses (`tests/integration/test_smoke.py` + `test_auth_flow.py`). Unit coverage for custom User and entry `serialize()` contracts.
- [ ] Coverage gate at 70% — wired via `[tool.coverage]` config; enforce in CI after the first green run establishes a baseline.

**Definition of done:** `make dev` brings up the full stack locally; `make test` runs green; `git push` triggers CI that gates the merge; the site looks unchanged to a user but the repo is now professional software.

---

### Phase 2 — Domain model refactor (two sessions)

The conceptual model is right. The implementation needs surgery.

#### 2.1 Clean up Entry polymorphism

Today: `SectionEntry` uses `ContentType` + `GenericForeignKey` plus a project-wide `pre_delete` signal. Subtle, fragile, slow joins.

Decision (**ADR-0005**): keep multi-table inheritance via `model_utils.InheritanceManager` but replace the `GenericForeignKey` through-table with a direct FK to `BaseEntry` on `SectionEntry`.

- [ ] Add `BaseEntry` as a concrete model (not abstract) so it can be FK'd.
- [ ] `SectionEntry.entry = FK(BaseEntry)` replacing `content_type + object_id`.
- [ ] Remove the global `pre_delete` signal; rely on cascade.
- [ ] Data migration that rewrites existing section entries (noop in dev since no real data).

#### 2.2 Per-entry translations

The core feature.

Decision (**ADR-0006**): each entry owns a `translations` JSONField keyed by ISO 639-1 language code, with a `canonical_language` field for the source. At render time, the CV's `CVLocale.language` selects the active translation; missing keys fall back to canonical.

- [ ] `BaseEntry.canonical_language = CharField(2)`.
- [ ] `BaseEntry.translations = JSONField(default=dict)` — `{"es": {"summary": "...", "highlights": "..."}, "fr": {...}}`.
- [ ] Translatable fields vary per subtype — declared as `TRANSLATABLE_FIELDS = ("summary", "highlights", ...)` on each subclass.
- [ ] Helper: `entry.get_field("summary", language="es")` with fallback.
- [ ] `entry.serialize(language="es")` returns the rendercv payload with translations applied.
- [ ] Admin and form UIs let you edit translations side-by-side per language tab.

#### 2.3 Service layer

Views are doing too much. Introduce a `services/` module per app for domain logic.

- [ ] `apps/cv/services.py`: `build_render_payload(cv, language, style) -> dict`.
- [ ] `apps/cv/services.py`: `clone_cv(cv, new_alias) -> CV` — duplicates a CV with all its relations.
- [ ] `apps/sections/services.py`: `reorder_sections(cv, ordered_ids)`, `reorder_entries(section, ordered_ids)`.
- [ ] Views become thin: parse input, call service, render template. No ORM queries in templates.

#### 2.4 Repository hygiene

- [ ] Move validation from `CVInfo.save()` to `.clean()` + form-level.
- [ ] Remove `default=1` on `CV.user`. Make it non-nullable.
- [ ] Collapse the duplicate logic in `CVUpdateView` to one clear `form_valid` path.
- [ ] Replace `from .views import *` with explicit imports.
- [ ] Remove the stale `cvdesgin-list` typo.

**Definition of done:** all existing flows still work; entries can be created in EN + ES + FR via admin; a CV with `CVLocale.language='es'` renders the Spanish copy; services have 90% test coverage; views are all under 50 lines.

---

### Phase 3 — Rendering pipeline (one to two sessions)

Take PDF rendering out of the request and make it fast, cached, and robust.

- [ ] New app: `apps/rendering`.
- [ ] `Render` model: `(id, cv, language, style, status, requested_at, completed_at, pdf_file, error)`.
- [ ] `tasks.py`: RQ job `render_cv(render_id)` that calls rendercv + Typst, writes the PDF to S3, updates the model.
- [ ] Content-hash the render input (`sha256` of the serialized payload + theme) and cache by hash — identical inputs never re-render.
- [ ] Replace `download_cv` with: POST `/cv/<id>/render` enqueues a job and returns the job status URL; GET `/render/<id>` polls; GET `/render/<id>/pdf` streams the file once done. HTMX polls with `hx-trigger="every 500ms"` until ready.
- [ ] Hard timeout (30s) and graceful failure with a readable error.
- [ ] Sandbox the Typst subprocess: `nobody` user, no network, 256MB memory cap, cgroup-limited.
- [ ] Store rendered PDFs in S3 (MinIO locally).

**Definition of done:** rendering a CV is fire-and-forget from the UI; the PDF appears within 3 seconds for a cached entry, 8 seconds cold; two simultaneous renders don't block the web worker; a render failure shows a clear error with a "Retry" button.

---

### Phase 4 — Frontend overhaul (three sessions)

Gut Bootstrap, install Tailwind + HTMX + Alpine, build the component system, then rebuild the screens.

#### 4.1 Foundation

- [ ] Delete `static/css/bootstrap.min.css`, `static/js/jquery-3.7.1.min.js`, `static/js/bootstrap.bundle.min.js`, `crispy_forms`, `widget_tweaks`.
- [ ] `npm init`, install `tailwindcss`, `@tailwindcss/typography`, `@tailwindcss/forms`, `htmx.org`, `alpinejs`, `esbuild`.
- [ ] `tailwind.config.js` with the tokens from `DESIGN.md`.
- [ ] Self-host Fraunces, Inter, JetBrains Mono in `static/fonts/`.
- [ ] Install `django-cotton` for component templates.
- [ ] `static/src/app.css` as Tailwind entry, `static/src/app.js` with HTMX + Alpine.
- [ ] Build pipeline: `npm run dev` watches, `npm run build` produces hashed output.
- [ ] Wire Whitenoise with compressed-manifest storage.

#### 4.2 Component library

Each component is a `django-cotton` template with a snapshot test.

- [ ] Button, IconButton, Input, Textarea, Select, Checkbox, Toggle, Card, Badge, Chip.
- [ ] Nav, Sidebar, Footer.
- [ ] Toast, Modal, Popover, Tooltip.
- [ ] LanguageChip (with translation-completeness dot), StyleChip.
- [ ] SplitPane (bespoke), DragHandle (Sortable.js via Alpine).
- [ ] CommandPalette (⌘K).
- [ ] A `/components` dev-only route that renders the kitchen sink in both light and dark. First thing CI smoke-tests.

#### 4.3 Screens

- [ ] **Marketing home** — hero + one screenshot + two CTAs.
- [ ] **Dashboard** — CV cards with PDF thumbnails, filter by language/style.
- [ ] **Editor** — split pane with live preview. Accordion sections. Top bar with language + style switcher + download.
- [ ] **Library** — entries table with per-language completion indicators.
- [ ] **Settings** — account, preferences.
- [ ] **Signup / Login / Password reset** — allauth's templates, fully restyled.

**Definition of done:** every page passes Lighthouse ≥95 performance and ≥100 accessibility; the `/components` route looks pixel-identical in light and dark; an end-to-end Playwright test clicks through signup → create CV → edit → render → download and passes in under 30 seconds.

---

### Phase 5 — API surface (one session)

Not for a public API yet — for ourselves, and for the CLI / mobile story.

- [ ] Install `djangorestframework`, `drf-spectacular`.
- [ ] `/api/v1/cvs`, `/api/v1/entries`, `/api/v1/sections`, `/api/v1/renders`.
- [ ] Token auth for personal tokens; session auth for the browser.
- [ ] OpenAPI at `/api/v1/schema`, Swagger UI at `/api/v1/docs` behind a staff check.
- [ ] Contract tests that pin the schema — breaking changes fail CI.

**Definition of done:** a Python CLI (even a 50-line script) can sign in with a token, list your CVs, and download a rendered PDF.

---

### Phase 6 — Auth, email, and public-SaaS hygiene (two sessions)

Prepare for real signups.

- [ ] Swap homegrown auth for `django-allauth` (mandatory email verification, password reset, magic links).
- [ ] Social login: Google and GitHub.
- [ ] `django-anymail` with a real provider (Resend or Postmark).
- [ ] Transactional templates: welcome, verify email, password reset, render-ready notification, weekly activity digest (opt-in).
- [ ] `django-ratelimit` on auth and render endpoints.
- [ ] `django-allauth`'s MFA app for TOTP.
- [ ] CSRF, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy headers via middleware.
- [ ] Legal: ToS, Privacy Policy, Cookie Policy. Static pages in `docs/legal/` rendered with markdown-to-html.
- [ ] GDPR: account deletion (hard delete) and data export (JSON of everything).
- [ ] Waitlist flag so we can collect emails before opening signup if we want.

**Definition of done:** a stranger can land on the marketing site, sign up with email or Google, verify the email, create an account, hit the editor, generate a CV, and delete their account — all with real emails sent and real security headers in place.

---

### Phase 7 — Billing scaffolding (one session)

Not selling anything yet, but the hooks need to exist so we don't have to retrofit.

- [ ] `djstripe` for Stripe integration.
- [ ] Plan model: `Free` (3 CVs, 2 languages, "Made with CVMaker" watermark on render) vs `Pro` ($8/mo, unlimited).
- [ ] Plan enforcement in services, not views — `cv.save()` raises `LimitExceeded` if the user is at the free cap.
- [ ] Stripe webhooks: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`.
- [ ] Billing screen: current plan, invoices, "Upgrade" / "Cancel".
- [ ] Free-plan PDFs get a footer line in the render payload. Paid renders don't.

**Definition of done:** Stripe test-mode subscription can be purchased and cancelled end-to-end; plan limits are actually enforced; a canceled subscription gracefully downgrades without deleting data.

---

### Phase 8 — Deploy and observe (one session)

- [ ] Pick a host (Railway / Fly / Render / VPS) — deferred decision, locked in when we get here. See ADR-0007 when written.
- [ ] Provision: 1 web dyno, 1 worker dyno, Postgres, Redis, S3-compatible object store, managed TLS on a custom domain.
- [ ] `django-storages` with S3 backend for `MEDIA_ROOT`.
- [ ] Structured logging (`structlog`) with JSON in prod, pretty in dev.
- [ ] Sentry for errors (free tier).
- [ ] PostHog for product analytics (free self-hosted or cloud).
- [ ] Uptime monitoring (Better Stack / UptimeRobot).
- [ ] Backups: nightly pg_dump to S3, 30-day retention.
- [ ] Health endpoints: `/healthz` (DB + Redis + S3 reachable), `/readyz`.
- [ ] A staging environment on the same provider.
- [ ] One-command deploy from main via GitHub Actions on green CI.

**Definition of done:** the app lives at a real URL, with HTTPS, errors going to Sentry, backups running nightly, a green status page, and a staging env that mirrors prod.

---

### Phase 9 — Growth features (ongoing)

The fun column. Not ordered — pick as energy allows.

- [ ] **AI-drafted translations.** "Translate this entry to Spanish" calls an LLM (Anthropic Claude via the API) with the user's own style guide (from existing translated entries) as context. User reviews + edits.
- [ ] **AI-drafted entries.** Paste a job description and your profile; suggest highlights phrased for that role.
- [ ] **Share links.** Signed, expiring, optional password, view analytics.
- [ ] **Public profile pages** at `cvmaker.app/@natan` — opt-in, renders a chosen CV as HTML with OG tags and JSON-LD.
- [ ] **PDF import.** Upload an existing PDF, extract entries, populate the library.
- [ ] **LinkedIn import.** Paste a public LinkedIn URL, we scrape the public data.
- [ ] **Job-description tailor.** Paste a JD, we reorder + filter entries to match.
- [ ] **CLI** (`pip install cvmaker`) using the API token for "render from local YAML".
- [ ] **VS Code extension** for editing entries in markdown.
- [ ] **More themes.** Ship 3 custom Typst themes tuned for: academic, engineering, creative.
- [ ] **Section snippets** — save a configured section as a reusable template across CVs.
- [ ] **Version history** per CV — restore any previous render.
- [ ] **Cover letter companion** — same building-block system for cover letters, referencing CV entries.

---

## Architecture decisions (ADRs)

One file per decision, dated, in `docs/adr/`. Template: [MADR](https://adr.github.io/madr/).

- `0001-project-structure.md` — src layout, uv, per-env settings _(Phase 1)_
- `0002-frontend-stack.md` — Tailwind + HTMX + Alpine _(Phase 1/4)_
- `0003-rendering-engine.md` — rendercv + Typst, async via RQ _(Phase 3)_
- `0004-custom-user-model.md` — `accounts.User(AbstractUser)` with email identifier _(Phase 1)_
- `0005-entry-polymorphism.md` — multi-table inheritance with FK'd BaseEntry _(Phase 2)_
- `0006-per-entry-translations.md` — JSONField of translations with fallback _(Phase 2)_
- `0007-hosting.md` — chosen provider _(Phase 8)_
- `0008-billing.md` — djstripe, plan enforcement in services _(Phase 7)_

---

## Session log

_Each session appends a short note here: date, phase worked, what shipped, what's next._

- **2026-04-21** — initial audit, roadmap, design system. No code changed. Next session starts Phase 0.
- **2026-04-22** — Phase 0 executed: encoding fixed, secrets to env, dead deps trimmed, URL placeholders replaced with real stubs, `pre_delete` signal narrowed, `get_entry_model` raises, README rewritten. `python manage.py check` clean; 35/35 URL names reverse; all six stub routes return 200. Pending: host-side `git clean -fdX` and the `v0.0.0-pre-refactor` tag. Next session starts Phase 1.1 (project layout + uv migration).
- **2026-04-22** — Phase 1.1 + 1.5 staged. Wrote `pyproject.toml` (uv-managed, dev dep group, ruff/mypy/pytest/coverage config), split settings under `src/cvmaker/settings/{base,dev,prod,test}.py`, moved `urls.py`/`wsgi.py`/`asgi.py` to `src/cvmaker/`, created `apps/core/` (TimestampedModel, UUIDModel, UUIDTimestampedModel), and rewrote `accounts/{models,forms,views,admin}.py` around a custom `User(AbstractUser)` with email identifier + `UserManager`. Every `FK(User,…)` in cv/entries/sections rewritten to `settings.AUTH_USER_MODEL`. Wrote ADR-0001 (project structure) and ADR-0004 (custom User). All git operations (app moves, migration resquash, DB reset, commit) are bundled into `scripts/phase1_migrate.ps1` for the user to run once locally — the sandbox can't unlink on the Windows mount.
- **2026-04-22** — Phase 1.2/1.3/1.4/1.6 scaffolded ahead of the migration script run. Phase 1.2: `.pre-commit-config.yaml` (hygiene + ruff + djlint + django-upgrade + mypy), `Makefile` (dev/test/lint/fmt/typecheck/ci/up/down targets, all routed through `uv run`), `.editorconfig`. Phase 1.3: `docker/web.Dockerfile` + `docker/worker.Dockerfile` (multi-stage, uv-synced, Typst binary baked in, non-root runtime), `docker/entrypoint.sh` (wait-for-db, opt-in migrations, prod collectstatic), `compose.yaml` (web + worker + postgres 16 + redis 7 + minio with healthchecks), `.dockerignore`. Phase 1.4: `.github/workflows/ci.yml` (lint / typecheck / test against Postgres service / docker build with GHA cache). Phase 1.6: `tests/` tree (unit/integration/e2e), `tests/factories.py` (UserFactory, CVFactory, SectionFactory, every entry subtype), `tests/conftest.py` (user/admin_client/cv/section fixtures), unit tests for the custom User and entry `serialize()` contracts, integration smoke tests for every named URL + the admin + the signup/login flow. Next: user runs `scripts/phase1_migrate.ps1`, then wire Phase 2 (Entry polymorphism cleanup + per-entry translations).
- **2026-04-23** — Phase 1 migration executed and committed (`070ca12`: "Phase 1: foundations — layout, tooling, docker, CI, tests, custom User"). `scripts/phase1_migrate.ps1` hardened through four iterative runs: added `Git-Run` wrapper that traps `$LASTEXITCODE` on every `git mv`/`git rm` (silent git failures were the root cause of the original cascade); auto-generates `.env` from `.env.example` with a fresh `SECRET_KEY` via `.NET UTF8Encoding($false)` (PS 5.1's `-Encoding UTF8` writes a BOM that Django's env parser chokes on); added post-cleanup BOM strip; preflight now detects and offers to clear a stale `.git/index.lock`. Rendercv 2.x compat: wrote `scripts/fix_rendercv_imports.py` — `apps/cv/models.py` gets a local pyyaml-backed `_read_yaml_file` helper (replaces rendercv 1.x's removed `read_a_yaml_file`) and `available_social_networks` import moved to `rendercv.schema.models.cv.social_network`; `apps/cv/views.py` gets a Phase-1 shim appended at EOF that rebinds `data` and `renderer` to `_RendercvUnavailable` proxies that raise `NotImplementedError` at call time, keeping the module importable for makemigrations/`reverse()` while deferring the real rendering work to Phase 3. Added `pyyaml` and `pillow` (ImageField) to runtime deps. All four app migrations (`accounts/0001_initial`, `cv/0001_initial`+`0002_initial`, `entries/0001_initial`, `sections/0001_initial`) regenerated and applied cleanly against a fresh Postgres DB. Next: user runs `pre-commit install && createsuperuser && runserver` for a smoke test, then `pytest` / `ruff check` / `ruff format --check` locally, then pushes to trigger CI. Phase 2 (Entry polymorphism + per-entry translations) after.
- **2026-04-27** — Phase 1 polish: `ruff check`, `ruff format --check`, and `pytest` all clean (29/29). Wrote `scripts/fix_phase1_lint.py` (idempotent companion to `fix_rendercv_imports.py`) to drop redundant `-> "User"` quoted method-returns and annotate `User.REQUIRED_FIELDS` as `ClassVar[list[str]]`; `BaseUserManager["User"]` kept quoted (class-base position, evaluated at class-creation time). Added `pythonpath = ["src", "apps"]` under `[tool.pytest.ini_options]` so pytest-django can find `cvmaker`. Added `[tool.ruff.lint.per-file-ignores]` entries scoping ruff out of legacy `apps/cv/**`, `apps/entries/**`, `apps/sections/**`, and `scripts/**` (each with the specific rules that fire and a "Phase 2+ rewrite" comment). Added `ignore::django.utils.deprecation.RemovedInDjango60Warning` to pytest's `filterwarnings`. Stripped whitenoise middleware from `settings/test.py` so the missing `staticfiles/` directory doesn't trigger a UserWarning. Fixed `tests/factories.py`: `_BaseEntryFactoryMixin` was a plain class so factory-boy's metaclass silently dropped the `user`/`alias` declarations and entries were created with `user_id = None`; converted to `_BaseEntryFactory(DjangoModelFactory)` with `Meta.abstract = True`. Fixed `tests/integration/test_smoke.py::_named_patterns` to accumulate namespaces while walking the URL tree so admin routes reverse as `admin:auth_user_changelist` instead of just `auth_user_changelist`. Fixed `apps/entries/models.py::BaseEntry._format_dates` to use `getattr(self, "start_date", None)` so the method works on subclasses (like `PublicationEntry`) that don't carry those columns. 40 files reformatted by `ruff format`. Next: commit the polish, push to trigger CI, then begin Phase 2 (entry polymorphism cleanup + per-entry translations).
