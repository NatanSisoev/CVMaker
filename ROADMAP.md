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

- [x] Add `BaseEntry` as a concrete model (not abstract) so it can be FK'd. _(already concrete from Phase 0)_
- [x] `SectionEntry.entry = FK(BaseEntry)` replacing `content_type + object_id`.
- [x] Remove the global `pre_delete` signal; rely on cascade.
- [x] Data migration that rewrites existing section entries (noop in dev since no real data).

#### 2.2 Per-entry translations

The core feature.

Decision (**ADR-0006**): each entry owns a `translations` JSONField keyed by ISO 639-1 language code, with a `canonical_language` field for the source. At render time, the CV's `CVLocale.language` selects the active translation; missing keys fall back to canonical.

- [x] `BaseEntry.canonical_language = CharField(2)`.
- [x] `BaseEntry.translations = JSONField(default=dict)` — `{"es": {"summary": "...", "highlights": "..."}, "fr": {...}}`.
- [x] Translatable fields vary per subtype — declared as `TRANSLATABLE_FIELDS = ("summary", "highlights", ...)` on each subclass.
- [x] Helper: `entry.get_field("summary", language="es")` with fallback.
- [x] `entry.serialize(language="es")` returns the rendercv payload with translations applied.
- [x] Admin and form UIs let you edit translations side-by-side per language tab. _(2026-10-08: `entry-translate` fragment on entry detail + editor inline form; admin unchanged)_

#### 2.3 Service layer

Views are doing too much. Introduce a `services/` module per app for domain logic.

- [x] `apps/cv/services.py`: `build_render_payload(cv, language, style) -> dict`.
- [x] `apps/cv/services.py`: `clone_cv(cv, new_alias) -> CV` — duplicates a CV with all its relations.
- [x] `apps/sections/services.py`: `reorder_sections(cv, ordered_ids)`, `reorder_entries(section, ordered_ids)`.
- [x] Views become thin: parse input, call service, render template. No ORM queries in templates. _(SectionManager moved out of models.py; section views simplified; CVUpdateView left for Phase 4 frontend rewrite, marked in 2.4)_

#### 2.4 Repository hygiene

- [x] Move validation from `CVInfo.save()` to `.clean()` + form-level.
- [x] Remove `default=1` on `CV.user`. Make it non-nullable. _(already non-null + no default after Phase 1.5 custom-user migration)_
- [x] Collapse the duplicate logic in `CVUpdateView` to one clear `form_valid` path. _(done 2026-10-07: shared `_SectionOrderMixin`)_
- [x] Replace `from .views import *` with explicit imports.
- [x] Remove the stale `cvdesgin-list` typo. _(audit finds no occurrences; presumably fixed in Phase 0)_

**Definition of done:** all existing flows still work; entries can be created in EN + ES + FR via admin; a CV with `CVLocale.language='es'` renders the Spanish copy; services have 90% test coverage; views are all under 50 lines.

---

### Phase 3 — Rendering pipeline (one to two sessions)

Take PDF rendering out of the request and make it fast, cached, and robust.

- [x] New app: `apps/rendering`.
- [x] `Render` model: `(id, cv, language, style, status, requested_at, completed_at, pdf_file, error)`. _(also `payload_hash`, `requested_by`)_
- [x] `tasks.py`: RQ job `render_cv(render_id)` that calls rendercv + Typst, writes the PDF to S3, updates the model. _(orchestration Phase 3.3; real rendercv 2.8 call wired 2026-10-07)_
- [x] Content-hash the render input (`sha256` of the serialized payload + theme) and cache by hash — identical inputs never re-render.
- [x] Replace `download_cv` with: POST `/renders/cv/<id>/` enqueues a job (cache-hit redirect to PDF, cache-miss 202 + polling fragment); GET `/renders/<id>/` polls; GET `/renders/<id>/pdf/` streams the file once done. HTMX polls with `hx-trigger="every 500ms"` until terminal. _(legacy `download_cv` left in place; cv.html template still uses it -- Phase 4 frontend rewrite swaps to the new flow)_
- [ ] Hard timeout (30s) and graceful failure with a readable error.
- [ ] Sandbox the Typst subprocess: `nobody` user, no network, 256MB memory cap, cgroup-limited.
- [x] Store rendered PDFs in S3 (MinIO locally).

**Definition of done:** rendering a CV is fire-and-forget from the UI; the PDF appears within 3 seconds for a cached entry, 8 seconds cold; two simultaneous renders don't block the web worker; a render failure shows a clear error with a "Retry" button.

---

### Phase 4 — Frontend overhaul (three sessions)

Gut Bootstrap, install Tailwind + HTMX + Alpine, build the component system, then rebuild the screens.

#### 4.1 Foundation

- [x] Delete `static/css/bootstrap.min.css`, `static/js/jquery-3.7.1.min.js`, `static/js/bootstrap.bundle.min.js`, `crispy_forms`, `widget_tweaks`. _(crispy-forms + widget_tweaks dropped from pyproject + INSTALLED_APPS; dead `{% load %}` tags stripped from 8 templates; static asset deletion runs in `scripts/phase4_1_setup.ps1`)_
- [x] `npm init`, install `tailwindcss`, `@tailwindcss/typography`, `@tailwindcss/forms`, `htmx.org`, `alpinejs`, `esbuild`. _(package.json drafted, user runs `npm install` via setup script)_
- [x] `tailwind.config.js` with the tokens from `DESIGN.md`.
- [ ] Self-host Fraunces, Inter, JetBrains Mono in `static/fonts/`. _(@font-face stanzas land in app.css; WOFF2 files added manually by user -- the variable-font download URLs are too fragile to script)_
- [x] Install `django-cotton` for component templates.
- [x] `static/src/app.css` as Tailwind entry, `static/src/app.js` with HTMX + Alpine.
- [x] Build pipeline: `npm run dev` watches, `npm run build` produces hashed output.
- [ ] Wire Whitenoise with compressed-manifest storage. _(already on; prod.py sets `whitenoise.storage.CompressedManifestStaticFilesStorage` -- just confirms the new dist files get hashed)_

#### 4.2 Component library

Each component is a `django-cotton` template with a snapshot test.

- [x] Button, IconButton, Input, Textarea, Select, Checkbox, ~~Toggle~~, Card, Badge, Chip. _(Toggle deferred — Checkbox covers the boolean case for now)_
- [x] Nav, ~~Sidebar~~, Footer. _(Sidebar lands when the editor screen rebuilds in 4.3 follow-up)_
- [x] Toast, Modal, ~~Popover, Tooltip~~. _(Popover + Tooltip deferred; not needed for the screens shipped in 4.3)_
- [~] LanguageChip (with translation-completeness dot), StyleChip. _(LanguageChip done 2026-10-08; StyleChip not needed yet — the editor's style select covers it)_
- [x] SplitPane (bespoke), DragHandle (Sortable.js via Alpine). _(SplitPane is inline Alpine in `cv/editor.html`; DragHandle is the global `x-sortable` directive in `app.js`)_
- [x] CommandPalette (⌘K). _(2026-10-08: `<c-command-palette>` + `palette` view)_
- [x] A `/components` dev-only route that renders the kitchen sink in both light and dark. First thing CI smoke-tests.

#### 4.3 Screens

- [x] **Marketing home** — hero + one screenshot + two CTAs.
- [x] **Dashboard** — CV cards (PDF thumbnails are a Phase 4.3 follow-up; needs the rendercv stub to be wired so we have a real PDF to thumbnail).
- [~] **Editor** — `/cv/<id>/editor/`: Alpine split pane (pointer + arrow-key resizable), language + style switchers, HTMX render -> inline PDF preview, section/entry outline linking to the entry pages. _(2026-10-07/08; drag-reorder + inline accordion entry editing done; translation tabs done)_
- [x] **Library** — Sections list + detail rebuilt with Cotton. _(Entries table with per-language completion indicators is a follow-up — the underlying `translations` data is there since Phase 2.2)_
- [x] **Settings** — account, preferences. _(2026-10-08: profile + password at `/accounts/profile/`; deletion/export stay in Phase 6)_
- [x] **Signup / Login** — restyled with the Cotton form atoms. _(Password reset is allauth-handled in Phase 6, restyled then)_

**Definition of done:** every page passes Lighthouse ≥95 performance and ≥100 accessibility; the `/components` route looks pixel-identical in light and dark; an end-to-end Playwright test clicks through signup → create CV → edit → render → download and passes in under 30 seconds.

---

### Phase 5 — API surface (one session)

Not for a public API yet — for ourselves, and for the CLI / mobile story.

- [x] Install `djangorestframework`, `drf-spectacular`.
- [x] `/api/v1/cvs`, `/api/v1/entries`, `/api/v1/sections`, `/api/v1/renders`. _(read-only + `POST cvs/{id}/render/` + `GET renders/{id}/pdf/`; write endpoints deferred until a client needs them)_
- [x] Token auth for personal tokens; session auth for the browser. _(tokens managed on Settings)_
- [x] OpenAPI at `/api/v1/schema`, Swagger UI at `/api/v1/docs` behind a staff check.
- [x] Contract tests that pin the schema — breaking changes fail CI. _(`docs/api/openapi.yaml` snapshot; `UPDATE_API_SCHEMA=1` to refresh)_

**Definition of done:** a Python CLI (even a 50-line script) can sign in with a token, list your CVs, and download a rendered PDF.

---

### Phase 6 — Auth, email, and public-SaaS hygiene (two sessions)

Prepare for real signups.

- [x] Swap homegrown auth for `django-allauth` (mandatory email verification, password reset, magic links). _(2026-10-08; magic links not enabled yet: `ACCOUNT_LOGIN_BY_CODE_ENABLED` is a one-line switch once real email is wired)_
- [~] Social login: Google and GitHub. _(wired: each provider installs itself when `GOOGLE_CLIENT_ID`/`GITHUB_CLIENT_ID` + `_SECRET` are set; needs the OAuth apps created)_
- [~] `django-anymail` with a real provider (Resend or Postmark). _(wired: `EMAIL_PROVIDER=resend|postmark` + key; needs an account and a verified sending domain)_
- [x] Transactional templates: welcome, verify email, password reset, render-ready notification, weekly activity digest (opt-in). _(all but the weekly digest, which needs a scheduler -- Phase 8)_
- [x] `django-ratelimit` on auth and render endpoints. _(2026-10-08)_
- [x] `django-allauth`'s MFA app for TOTP. _(TOTP + recovery codes, linked from Settings)_
- [x] CSRF, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy headers via middleware. _(Permissions-Policy added 2026-10-08; the rest were already in prod.py)_
- [ ] Legal: ToS, Privacy Policy, Cookie Policy. Static pages in `docs/legal/` rendered with markdown-to-html.
- [x] GDPR: account deletion (hard delete) and data export (JSON of everything). _(2026-10-08, Settings page)_
- [x] Waitlist flag so we can collect emails before opening signup if we want. _(`SIGNUP_MODE=waitlist`, 2026-10-08)_

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
- **2026-04-27** — Phase 1 polish: `ruff check`, `ruff format --check`, and `pytest` all clean (29/29). Wrote `scripts/fix_phase1_lint.py` (idempotent companion to `fix_rendercv_imports.py`) to drop redundant `-> "User"` quoted method-returns and annotate `User.REQUIRED_FIELDS` as `ClassVar[list[str]]`; `BaseUserManager["User"]` kept quoted (class-base position, evaluated at class-creation time). Added `pythonpath = ["src", "apps"]` under `[tool.pytest.ini_options]` so pytest-django can find `cvmaker`. Added `[tool.ruff.lint.per-file-ignores]` entries scoping ruff out of legacy `apps/cv/**`, `apps/entries/**`, `apps/sections/**`, and `scripts/**` (each with the specific rules that fire and a "Phase 2+ rewrite" comment). Added `ignore::django.utils.deprecation.RemovedInDjango60Warning` to pytest's `filterwarnings`. Stripped whitenoise middleware from `settings/test.py` so the missing `staticfiles/` directory doesn't trigger a UserWarning. Fixed `tests/factories.py`: `_BaseEntryFactoryMixin` was a plain class so factory-boy's metaclass silently dropped the `user`/`alias` declarations and entries were created with `user_id = None`; converted to `_BaseEntryFactory(DjangoModelFactory)` with `Meta.abstract = True`. Fixed `tests/integration/test_smoke.py::_named_patterns` to accumulate namespaces while walking the URL tree so admin routes reverse as `admin:auth_user_changelist` instead of just `auth_user_changelist`. Fixed `apps/entries/models.py::BaseEntry._format_dates` to use `getattr(self, "start_date", None)` so the method works on subclasses (like `PublicationEntry`) that don't carry those columns. 40 files reformatted by `ruff format`. Committed as `3000171` and pushed (after PAT was re-issued with the `workflow` scope and the pre-commit ruff rev was bumped from `v0.8.4` → `v0.9.10` so it knows `RUF059`; mypy moved to `stages: [manual]` so it's invocable on demand without blocking commits).
- **2026-04-27** — Phase 2.1 + ADRs landed (code only; user runs `scripts/phase2_1_migrate.ps1` to generate + apply the migration). Wrote ADR-0005 (entry polymorphism via direct FK) and ADR-0006 (per-entry translations via JSONField). Replaced `SectionEntry.content_type + object_id + GenericForeignKey` with `SectionEntry.entry = FK(BaseEntry, on_delete=CASCADE, related_name="section_entries")`; deleted the `pre_delete` signal block, `_ENTRY_MODELS` tuple, and `_delete_dangling_section_entries` from `apps/sections/models.py`. Added `unique_together = ("section", "entry")` so the same entry can't appear twice in one section. Added `Section.serialize(language=None)` and `SectionEntry.serialize(language=None)` with subclass promotion via `BaseEntry.objects.select_subclasses()`; added `_promote_in_order()` helper that batches the promotion in one query. Added `SectionEntry.real_entry` property for templates and one-off view code that need the concrete subclass. Updated all `serialize()` methods on entry subclasses to accept (and currently ignore) a `language` kwarg — Phase 2.2 wires the actual translation lookup. Rewrote `apps/sections/forms.py` to use plain BaseEntry UUIDs in the multi-choice picker (no more `ct_id::object_id` keys). Refactored `apps/sections/views.py` to extract a `_SectionEntryWriter` mixin so Create + Update share the entry-write loop. Updated `apps/cv/views.py::CVUpdateView.get_context_data` to promote entries up-front via one batched `select_subclasses()` query, replacing the per-entry `content_object` access. Updated three templates (`sections/list.html`, `sections/detail.html`, `cv/edit.html`) to use `entry.entry`, `entry.real_entry`, and `entry.entry.id` instead of `entry.content_object*`. `SectionManager` (the YAML import helper used by `cv/views.py`) stays in `sections/models.py` for now with the FK update; Phase 2.3 moves it to `apps/sections/services.py`. Wrote `scripts/phase2_1_migrate.ps1` to drive `makemigrations sections → migrate → check → pytest` in one shot. The auto-detector tripped on the non-nullable `entry` field needing a default for any existing rows, so I wrote `apps/sections/migrations/0002_sectionentry_entry_fk.py` by hand (AddField nullable → RunPython backfill → AlterField non-nullable → RemoveField content_type+object_id → AlterUniqueTogether). Phase 2.1 committed and pushed. djlint hooks moved to `stages: [manual]` because the legacy Bootstrap templates trip a batch of T002/T003/H021/H029 rules that Phase 4 (Tailwind+Cotton rewrite) overwrites.
- **2026-04-27** — Phase 2.2 landed (per-entry translations, ADR-0006). Added `BaseEntry.canonical_language = CharField(max_length=2, default="en")` and `BaseEntry.translations = JSONField(default=dict, blank=True)`. Each subclass declares its own `TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]]` — Education translates `area`/`degree`/`location`/`summary`/`highlights` (not `institution`); Experience translates `position`/`location`/`summary`/`highlights` (not `company`); Publication translates `title`/`journal` (not `authors`); the simple-content subclasses (Bullet, Numbered, ReversedNumbered, Text, OneLine) translate their full content. Added `BaseEntry.get_field(name, language=None)` with the ADR-spec'd fallback rules (canonical when `language` is None or matches `canonical_language`; explicit translation when present even if empty; canonical fallback otherwise). Added `BaseEntry.clean()` that rejects non-dict translations, non-ISO-639-1 keys, non-dict inner bags, and unknown field names — typos like `"summarry"` get caught at form-submit time instead of silently shadowing render output. Rewrote every subclass's `serialize()` to route translatable columns through `get_field`. Wired `cv.locale.language` through `CV.serialize → Section.serialize → SectionEntry.serialize → BaseEntry.serialize` so a CV with `CVLocale.language="es"` renders the Spanish copy automatically. Wrote `apps/entries/migrations/0002_entry_translations.py` (auto-generatable but written by hand for visibility). Added `tests/unit/test_translations.py` — 22 tests covering `get_field` fallback, per-subclass `serialize(language=)` behaviour, `clean()` validation paths, and the `TRANSLATABLE_FIELDS` declarations as a regression guard. 49/49 tests passing. Phase 2.2 committed and pushed.
- **2026-04-27** — Phase 4.2 + 4.3 (partial) landed. Wired django-cotton into Django's template engine — `APP_DIRS=False` is required for an explicit `loaders` list, so I rebuilt the loader chain with `cached.Loader` wrapping `cotton_loader.Loader` + `filesystem.Loader` + `app_directories.Loader` (preserving per-app template discovery). Cotton's templatetag is registered as a `builtins` so every template can use `<c-foo>` without `{% load %}`. Built 13 Cotton components under `templates/cotton/`: form atoms (input, textarea, select, checkbox), pressables (button with 4 variants × 3 sizes × link/button modes, icon-button), surfaces (card with header/footer slots, badge with 3 variants, chip with optional dismiss), overlays (modal — Alpine-driven, Esc-to-close, accessible-by-default with aria-modal + aria-labelledby; toast — event-driven via `$dispatch('toast', {...})` with auto-dismiss after 4s), and layout primitives (nav, footer). Rewrote `templates/base.html` to use `<c-nav />`, `<c-footer />`, `<c-toast />` and the new `static/dist/app.css` / `static/dist/app.js` bundles; dropped the jQuery + Bootstrap script tags and the Google Fonts link. Rewrote `templates/homepage.html` (hero + two CTAs + explainer SVG, all utility classes), `templates/placeholder.html` (cleaner empty-state), `accounts/login.html` + `accounts/signup.html` (Cotton form atoms with error states), `cv/list.html` (dashboard with cards + modal delete + render button hooked to `rendering:enqueue`), `sections/list.html` + `sections/detail.html` (Cotton cards + chip-per-entry + modal delete), and `rendering/_status.html` (HTMX polling fragment with the new design language; existing rendering tests' `b"hx-get="` + `b"Retry"` assertions still pass). Built `templates/components.html` -- the kitchen-sink visual reference. Wired `/components/` as a dev-only route via `_components_view` that 404s when DEBUG=False; the URL stays registered in all environments so tests can hit it. Added two smoke tests: one flips DEBUG=True per-test and asserts the kitchen-sink renders with key fragments (`b"Primary"`, `b"font-display"`), the other asserts a 404 in the default test-DEBUG=False setting. **Outstanding follow-up** (Phase 4.3 continuation): CV detail/edit/form/delete + the 16 CVInfo/CVDesign/CVLocale/CVSettings templates + entry list/detail/form/update + 8 entry-type field includes + the real Editor screen (heaviest, needs SplitPane + DragHandle components) + the Settings screen (needs new view + template) + LanguageChip/StyleChip/CommandPalette/Popover/Tooltip components. These all stay on Bootstrap markup that Tailwind treats as no-op classes -- pages render but unstyled until each template gets the Cotton rewrite. Next: user runs `scripts/phase4_1_setup.ps1` (still the right entrypoint — same npm install + uv sync + check + pytest cycle), then `git add && commit && push`.

- **2026-04-27** — Phase 4.1 scaffolded (foundation; user runs `scripts/phase4_1_setup.ps1` to actuate the Windows-side bits). Created `package.json` with Tailwind 3.4 + @tailwindcss/forms + @tailwindcss/typography + htmx.org 2.x + alpinejs 3.x + esbuild + concurrently; `npm run dev` watches both pipelines, `npm run build` minifies for prod. Wrote `tailwind.config.js` with the DESIGN.md tokens hand-translated: 8pt spacing scale (named stops only, no off-grid temptation), Fraunces/Inter/JetBrains Mono font stacks, 1.25 minor-third type scale 12→60px, 4 radius levels (sm/md/lg/full), 3 elevation steps + a focus-ring shadow. Color tokens are CSS variables (`var(--bg)` etc.) so dark mode is one `data-theme="dark"` flip on `<html>`, not a Tailwind variant rebuild; the `darkMode: ['selector', '[data-theme="dark"]']` strategy gates the variant on the same attribute. Tokens defined in `static/src/app.css`'s `@layer base` block: light + dark palettes from DESIGN.md, `@font-face` stanzas with `font-display: swap` and variable-font format hints. `static/src/app.js` is the JS entry -- imports `htmx.org` and `alpinejs` (windowed for x-data resolution), wires Django CSRF into HTMX's `htmx:configRequest` event for state-mutating verbs, owns a `window.toggleTheme()` helper that persists to localStorage and falls back to `prefers-color-scheme`. Removed `django-crispy-forms` and `django-widget-tweaks` from runtime deps; added `django-cotton>=1.4,<2`. Dropped `crispy_forms` + `widget_tweaks` from `THIRD_PARTY_APPS` (replaced with `django_cotton`); removed `CRISPY_TEMPLATE_PACK = "bootstrap5"`. Stripped dead `{% load crispy_forms_tags %}` and `{% load widget_tweaks %}` directives from 8 templates -- they were dead loads, no actual filter usage. Wrote `scripts/phase4_1_setup.ps1` to drive the Windows-side actions the Linux sandbox can't run: remove legacy Bootstrap/jQuery files, `npm install`, `npm run build`, `uv sync`, `manage.py check`, `pytest`. Fonts (variable WOFF2 for Fraunces/Inter/JetBrains Mono) still need manual placement in `static/fonts/` -- the download URLs are too fragile to script reliably. Next: user runs `scripts/phase4_1_setup.ps1`, drops the three WOFF2 files in `static/fonts/`, commits + pushes. Then Phase 4.2 (component library) builds out Button/Card/Input/Modal/etc. as `templates/cotton/` partials with a `/components` dev-only kitchen-sink route as the visual regression target.

- **2026-04-27** — Phase 3.6 closes (ADR-0007 + audit of existing tests). Wrote ADR-0007 (`docs/adr/0007-rendering-pipeline.md`) covering: (1) RQ over Celery (smaller surface, no broker-side scheduling, faster startup, plain-function task entry points are unit-testable without a harness), (2) SHA-256 over canonical-JSON cache key with `style` and `language` participating as first-class inputs not just transitively via the payload (caught the CV-without-CVLocale collision in Phase 3.2 testing), (3) three sandbox layers (container non-root + no-network policy, subprocess `shell=False` with 30s timeout, queue-level RQ timeout of 35s = 30s Typst hard cap + 5s orchestration slack), (4) signed-S3-URL storage with 1-hour TTL. Documented the full request/worker/poll lifecycle as ASCII flow. Decision section is precise about what we deliberately accept (two simultaneous identical requests both enqueue jobs; the cache hit only triggers on `done`; cache hash is deterministic but not invariant against payload-schema changes). The originally-spec'd "integration test that actually runs Typst" is parked until the rendercv 2.x integration lands in `_render_payload_to_pdf`; the 27 existing rendering tests (16 hash/cache/task in `test_rendering.py`, 11 view-level in `test_rendering_views.py`) cover everything else with mocked rendercv. **Phase 3 closes. DoD review**: ✅ rendering is fire-and-forget from the UI (POST /renders/cv/<id>/ -> 202 + polling fragment, or 302 to cached PDF); ✅ identical inputs never re-render (content-hash cache); ✅ two simultaneous renders don't block web workers (queue-decoupled); ✅ render failure shows a readable error with a Retry button. **Outstanding follow-up** (not blocking Phase 4): replace `_render_payload_to_pdf` stub with the real rendercv 2.x call once the upstream API stops shifting. Next phase: 4.1 (Tailwind+HTMX+Alpine foundation).

- **2026-04-27** — Phase 3.5 landed (S3/MinIO storage). Added `django-storages[s3]>=1.14,<2` and `boto3>=1.35,<2` to runtime deps. Centralized S3 config in `settings/base.py`: every `AWS_*` env var is read once, `_s3_storage_options()` returns the shared OPTIONS dict so dev and prod consume identical configuration surface (only the endpoint URL changes between them). `dev.py`: storage flips to MinIO when `AWS_S3_ENDPOINT_URL` is set in the env (compose mode), falls back to filesystem otherwise (bare `runserver`). `prod.py`: storage is unconditionally S3-backed; raises `RuntimeError` at boot if `AWS_STORAGE_BUCKET_NAME` is empty -- fail loud, not silent-write-to-disk. Signed-URL TTL = 1 hour (`AWS_QUERYSTRING_EXPIRE`); `file_overwrite=False` so two renders with different content but the same target name don't silently clobber. Documented the storage trio (MinIO via compose / FS via bare runserver / S3 in prod) in README under "Object storage". Updated the "Development notes" section to reflect Phase 3 -- rendering is queued, not in-thread; spin up the worker via `docker compose up worker`.

- **2026-04-27** — Phase 3.4 landed (async render views + HTMX polling). Implemented the three view functions in `apps/rendering/views.py`: `enqueue_render_view` (POST, `@login_required`+`@require_POST`, `get_object_or_404(CV, pk, user=request.user)` so non-owners get 404 instead of 403 -- doesn't leak existence; on cache hit redirects 302 to the PDF, on cache miss returns the polling fragment with status 202), `render_status_view` (GET, returns the same fragment for HTMX self-polling), `render_pdf_view` (GET, returns 404 if not done, otherwise `FileResponse` streaming the PDF via the configured storage backend). Centralized the auth check in `_get_owned_render(user, render_id)` -- one definition of "owned via cv.user", filters at query time so render-id enumeration via the URL is impossible. Wrote `apps/rendering/templates/rendering/_status.html` -- the polling fragment uses `hx-get`/`hx-trigger="every 500ms"`/`hx-swap="outerHTML"` while in flight; once terminal the next response has no `hx-trigger` so polling stops automatically. Done state shows a download link; failed state shows the captured error in a `<pre>` plus a Retry button (`hx-post` to enqueue, swapping the fragment in place). Moved the URL prefix from `/cv/<id>/render/` to `/renders/cv/<id>/` to avoid colliding with `cv.urls`'s ownership of `/cv/`. Added `tests/integration/test_rendering_views.py` -- 11 tests covering enqueue (anon redirect, owner gets 202 with `hx-get` fragment, non-owner 404, cache-hit 302 to PDF), status (owner gets fragment with `hx-trigger`, non-owner 404, terminal-done drops `hx-trigger` and shows download link, terminal-failed shows error+retry), pdf (404 when not done, 404 for non-owner, streams `application/pdf` content with the actual bytes through `InMemoryStorage`). Next: user runs `uv run pytest -q && commit && push`. The legacy `cv-download` route in `cv.urls` stays for now -- Phase 4 frontend rewrite will swap the CV detail template's "Download" button to a `hx-post` against `rendering:enqueue`, then we delete the old function. Phase 3.5 (S3/MinIO storage) and 3.6 (ADR-0007 + integration smoke that actually invokes Typst) follow.

- **2026-04-27** — Phase 3.3 landed (RQ task orchestration; real rendercv call deferred). Added `django-rq>=3.0,<4` and `rq>=2.0,<3` to runtime deps. Configured `RQ_QUEUES` in `settings/base.py` with a dedicated `render` queue (35s timeout = 30s Typst hard cap + 5s orchestration slack) and a `default` queue reserved for later phases. In `settings/test.py`: set `RQ_QUEUES[*]["ASYNC"] = False` so jobs run inline in the test process; switched `STORAGES["default"]` to `django.core.files.storage.InMemoryStorage` so PDF writes don't pollute the filesystem between runs. Wrote `apps/rendering/tasks.py::render_cv(render_id)` -- loads the row with `select_related("cv__locale")` (one query, not three), short-circuits on already-terminal status (idempotent against duplicate enqueues / worker retries), promotes to `running`, calls `build_render_payload`, hands the payload to `_render_payload_to_pdf`, on success writes via `pdf_file.save(filename, ContentFile(pdf_bytes), save=False)` and flips to `done` with `completed_at`. Two error paths: a user-readable `_RenderError` stores its message verbatim in `Render.error`; an unexpected `Exception` stores a generic message + re-raises so RQ records the failure for ops dashboards (no internals leak to the UI). The actual rendercv 2.x call is a stub -- raises a clear "not wired yet" RenderError; the orchestration around it is real and tested. Hooked `_dispatch_render_job` into `services.enqueue_render` (lazy `import django_rq` so the import graph doesn't pull Redis at module-load time, which would crash `manage.py check` without a reachable broker). Updated `docker/worker.Dockerfile` CMD to `python manage.py rqworker render`. Added 5 tests in `TestRenderCv` covering the success/RenderError/unexpected-Exception/already-terminal/missing-id paths via `monkeypatch.setattr` on `_render_payload_to_pdf`. Existing enqueue tests get an `autouse` fixture stubbing `_dispatch_render_job` so they don't trip the not-yet-wired stub. Next: user runs `uv sync && uv run python manage.py check && uv run pytest -q`. If green, commit + push. Then Phase 3.4 (HTMX-driven enqueue/poll/stream views) and 3.5 (S3/MinIO) -- both lighter than 3.3. The real rendercv 2.x integration is its own follow-up once the upstream API stops shifting.

- **2026-04-27** — Phase 3.1 + 3.2 scaffolded (rendering app + content-hash cache). Created `apps/rendering/` with `apps.py`, `models.py`, `admin.py`, `urls.py`, `views.py` (501 placeholders for 3.4), and a hand-written `migrations/0001_initial.py` (avoiding the Windows `makemigrations` round-trip). The `Render` model carries `cv` (FK), `language`, `style`, `payload_hash` (db_index), `status` (queued/running/done/failed, db_index), `requested_at`, `completed_at`, `pdf_file`, `error`, and `requested_by` (FK to User, SET_NULL for shared-CV futures). Composite index on `(payload_hash, status)` so the cache hot-path is one bounded scan. Wrote `apps/rendering/services.py` with `compute_payload_hash(payload, style)` (SHA-256 over `json.dumps(sort_keys=True, separators=(',', ':'), default=str, ensure_ascii=True)` plus a `|style=...` suffix -- determinism guarantees: dict ordering doesn't matter, whitespace doesn't matter, dates/UUIDs/Paths cast cleanly via `default=str`, output is platform-independent ASCII), `enqueue_render(cv, language, style, requested_by)` (cache lookup short-circuits to a `done` Render with matching hash; cache miss creates a fresh `queued` row -- Phase 3.3 wires the actual RQ dispatch), and `fetch_render(render_id)` (polling accessor returning None on missing). Wired `rendering` into `LOCAL_APPS` and `rendering.urls` into the root urlconf with `namespace="rendering"`. Added `tests/unit/test_rendering.py` -- 16 tests across hash determinism (identical-input/dict-ordering/style-sensitivity/non-JSON-types), enqueue (queued/cached/failed-doesn't-cache/different-language-different-row), fetch, and `is_terminal`. Cache-hit test stamps `pdf_file.name` directly to bypass storage I/O. Next: user runs `uv run python manage.py migrate && uv run pytest -q && commit && push`. Then Phase 3.3 (RQ task + Typst sandbox) is the real work; 3.4 (HTMX polling), 3.5 (S3/MinIO), 3.6 (ADR-0007) follow.

- **2026-04-27** — Phase 2.4 hygiene pass. Replaced `from .views import *` in `apps/cv/urls.py` and `apps/entries/urls.py` with explicit imports — both files now declare exactly what symbols urlpatterns binds. Moved `CVInfo`'s social-networks allow-list check from `save()` (which validated *after* the row was written, a partial-write hazard) to `clean()` (called by Django form/admin via `full_clean()` before save). Improved the validation message to list the offending networks and the supported set, surfaced under the `social_networks` field key so forms render the error in-context. Fixed `apps/cv/views.py`'s `from cvmaker import settings` → `from django.conf import settings` — the old form imported the *settings module package* rather than the runtime config, working only by accident because `cvmaker.settings.dev` happened to set the right values at import time. Audit found no `cvdesgin` typos remaining (Phase 0 caught them) and `CV.user` is already non-null with no default. `CVUpdateView`'s duplicate `form_valid` paths stay -- Phase 4 (Tailwind+Cotton+HTMX rewrite) replaces the whole edit surface, so investment now is wasted. Phase 2 closes (DoD): all existing flows still work; entries can be created in EN+ES+FR via translations dict; `CVLocale.language="es"` renders the Spanish copy; services have direct unit tests covering happy + error paths.

- **2026-04-27** — Phase 2.3 landed (service layer extraction). Created `apps/cv/services.py` with `build_render_payload(cv, language=None, style=None)` (thin wrapper over `CV.serialize` that allows ad-hoc language overrides without persisting CVLocale changes; the override is rolled back in a try/finally) and `clone_cv(cv, new_alias)` (transactional clone — per-CV singletons CVInfo/CVDesign/CVLocale/CVSettings are duplicated as fresh rows, sections are *shared* since they're user-owned and legitimately appear in many CVs, CV-Section through-rows are recreated to preserve order). Added `_copy_or_none` helper that re-fetches the source row before mutating its pk to None, so the caller's Python reference doesn't get clobbered (a subtle bug in the naive idiom). Created `apps/sections/services.py` with `reorder_sections(cv, ordered_ids)`, `reorder_entries(section, ordered_ids)` (both `@transaction.atomic`, both raise `DoesNotExist` rather than silently no-op on a bad id, both accept either UUID instances or strings via a `_coerce_uuid` helper), and `import_sections_from_data_model(user, cv, data_model, alias)` — which fully replaces `SectionManager` from `apps/sections/models.py`. Updated `apps/cv/views.py::CVImportYamlView` to call the import service directly. Simplified `apps/sections/views.py` — dropped the Phase 2.1 `_SectionEntryWriter` mixin and the duplicate Create/Update entry-write loops; `SectionForm.save_m2m` already does ordering correctly so the views are now plain Django CBVs. Added `tests/unit/test_services.py` covering `build_render_payload` (top-level keys, side-effect-free language override), `clone_cv` (alias, new pk, singletons copied, sections shared, order preserved), `reorder_sections`/`reorder_entries` (rewriting the order columns, DoesNotExist on bad ids), and `import_sections_from_data_model` (skip-on-no-sections happy path, full create-with-entries happy path with a synthetic SimpleNamespace data model). `CVUpdateView`'s legacy if/elif tower over `EducationEntry/ExperienceEntry/PublicationEntry` stays as-is — Phase 4 (Tailwind+Cotton+HTMX rewrite) replaces the whole edit surface with per-entry partials, so investing in a service-side dispatch table now would be wasted. Next: user runs `uv run pytest -q && git add -A && git commit && git push`. Then Phase 2.4 (hygiene: nullable=>required CV.user, validation move from save→clean, drop the `cvdesgin-list` typo, replace `from .views import *`).

- **2026-10-07** — Phase 4.3 continuation. Fixed the one red test left from 4.2: Cotton resolves `<c-icon-button>` to `icon_button`, so `templates/cotton/icon-button.html` was renamed to `icon_button.html` (this also fixes the dashboard and section detail, which use it). Rewrote `cv/detail.html` and the CVInfo/CVDesign/CVLocale/CVSettings `*_list.html` + `*_confirm_delete.html` templates (9 files, on Cotton card/button/modal; the list pages replace the Bootstrap modals with the Alpine modal; the detail page's Download link now posts to `rendering:enqueue`). Added smoke tests that render the five list pages and the CV detail page for a logged-in user. 106 tests green. **Still on Bootstrap markup:** the 4 `cv*_detail.html` pages, `entries/{list,detail,update}.html` + the 8 `includes/*_fields.html`, `cv/edit.html`, `sections/form.html`, the `*_form.html` pages (partly), and `templates/includes/{nav,footer}.html` (dead if unused). Next: those, then Editor/SplitPane (the heavy one), fonts in `static/fonts/`, and nothing committed yet -- the whole 4.1-4.3 working tree is uncommitted.

- **2026-10-07 (cont.)** — Phase 4.3 template sweep finished: no Bootstrap markup remains in `apps/` or `templates/`. Converted the four `cv*_detail.html`, all `*_form.html` (CVInfo/Design/Locale/Settings, `cv/form.html`, `sections/form.html`, `entries/{form,update,detail,list}.html`), `cv/edit.html`, and the 9 `entries/includes/*_fields.html` partials. Deleted three orphaned files (`templates/includes/{nav,footer}.html`, `cv/includes/cv_list_item.html`). **Found + fixed a latent break:** six form templates called `{% render_field %}` from `django-widget-tweaks`, which Phase 4.1 removed (the "dead load" strip was wrong for them), so every create/edit form would have raised `TemplateSyntaxError`. Replaced with shared `templates/includes/form_field.html` + `form_fields.html` and a `.cv-form` scoped style in `app.css` (Django widgets are bare inputs). Old `{% block extra_js %}` modals were also dead (base.html has no such block); they are now Cotton modals. 13 new smoke tests render every converted page with data. **Latent bug found and fixed:** `CVUpdateView` (`cv-edit`) 500ed -- it called `CVInfo.objects.get_or_create(cv=cv)` but `CVInfo` has no `cv` field, `post()` repeated it, and the view rendered `cv/form.html` while building context for a different template. Reduced it to a plain owner-scoped `UpdateView` over `CVForm` sharing a `_SectionOrderMixin` with `CVCreateView` (writes `CVSection` rows from `section_order`, drops other users' sections); `CVCreateView` also gained `LoginRequiredMixin` and per-user FK querysets (previously every user's info/locale/design appeared in the dropdowns). The orphaned `cv/edit.html` was deleted; this closes the Phase 2.4 `CVUpdateView` item. Per-entry editing stays on the entries pages until the Editor screen merges them. 121 tests green. Still open in 4.3: Editor/SplitPane/DragHandle, Settings screen, LanguageChip/StyleChip/CommandPalette, fonts in `static/fonts/`.

- **2026-10-07 (cont. 2)** — Real rendering wired (closes the Phase 3 stub). `_render_payload_to_pdf` now writes the payload as YAML into a temp dir, builds the rendercv 2.8 model (`build_rendercv_dictionary_and_model`), and runs `generate_typst` + `generate_pdf` (PNG/HTML/Markdown disabled); the scratch dir is deleted afterwards. `_to_rendercv_2x` renames `rendercv_settings` -> `settings` (the 1.x key), drops None blocks, and applies the render's `style` as a theme override without touching the stored CVDesign. rendercv validation errors are flattened with their schema location into the user-visible `Render.error`; a CV with no info fails with a plain-language message. **Dependency fix:** `rendercv` alone doesn't install `typst-py`; Phase 0's "dead dep" trim removed it, so pyproject now pins `rendercv[full]>=2.8`. Also removed a stray `pprint.pprint(final)` from `CV.serialize` and made it tolerate a CV with no info. 5 new tests in `tests/integration/test_render_real.py` run the real pipeline (valid PDF, theme override changes output, no-info message, invalid-email message, worker entry point stores a PDF through storage). 126 tests green. **Caveats:** rendercv requires one entry type per section, so a section mixing e.g. Experience and Education entries fails validation (surfaced to the user, but the section editor doesn't prevent it yet); the 30s cap is the RQ queue timeout (35s) rather than a killable subprocess, and the nobody-user/cgroup sandbox item is still open. The `typst` binary baked into the Dockerfiles is now redundant.

- **2026-10-07 (cont. 3)** — Editor screen + render-flow hardening. `SectionForm.clean_entries` now rejects sections that mix entry kinds (rendercv requires one kind per section), with a message telling the user to split them. New `cv.services.available_languages(cv)` (locale language first, then every canonical/translation code on the CV's entries). New `CVEditorView` (`cv-editor`, login + owner-scoped, 404 for others) and `cv/editor.html`: top bar with language + style selects (the `custom` theme excluded) and *Render preview*, left outline of sections/entries, keyboard-accessible separator (`role="separator"`, left/right arrows), right pane that receives the HTMX render fragment. Rendering views: an HTMX cache hit used to 302 to the PDF, which HTMX would follow and swap raw PDF bytes into the page; HTMX callers now get the fragment (200) while plain form posts still redirect. A `preview=1` flag threads through POST, the polling URL and the Retry form, and makes the done state embed an `<iframe>` of the PDF. Dashboard and CV detail now link to the editor; `cv-edit` remains the CV-settings form. 135 tests green. **Not verified in a browser** (needs Redis + `rqworker render` running); the HTMX/Alpine behaviour is covered only at the HTML level. Next: drag-reorder (Sortable via Alpine, backed by `reorder_sections`/`reorder_entries`), inline entry editing, LanguageChip with translation-completeness dot, Settings screen, fonts.

- **2026-10-07 (cont. 4)** — Drag-reorder in the Editor. New owner-scoped POST endpoints `cv-reorder-sections` (`/sections/cv/<cv_id>/order/`) and `section-reorder-entries` (`/sections/<id>/entries/order/`) take repeated `ids`, call `reorder_sections`/`reorder_entries` inside one transaction, return 204, and return 400 (with nothing written) for an empty list, an unparsable id, or an id not attached to that CV/section; 404 for other users' objects. Sortable.js is now bundled via npm (dropping the jsDelivr `<script>` in `cv/form.html`, whose inline init now waits for `DOMContentLoaded` so the deferred bundle has loaded) and exposed through a global Alpine `x-sortable="<url>"` directive: drag by `[data-drag-handle]`, POST the new order, and on failure restore the previous DOM order and show an error toast; success fires `sortable-saved`, which the editor turns into an "Order saved, render again" toast. 11 new tests (`tests/integration/test_reorder_views.py`). 146 tests green. Still not exercised in a real browser.

- **2026-10-08** — Inline entry editing in the Editor (autonomous loop). New `EntryInlineEditView` (`entry-inline`, `/entries/<id>/inline/`, owner-scoped via `EntryBaseView`) returns the entry's type-specific form as an HTMX fragment (`entries/_inline_form.html`, reusing `includes/form_fields.html`). A valid POST saves and fires a success toast through the `HX-Trigger` header; an invalid POST re-renders with errors at 200 (HTMX skips 4xx swaps) and saves nothing. In `cv/editor.html` each entry row is now an accordion toggle (`aria-expanded`/`aria-controls`) whose panel lazy-loads the form on first open (`hx-trigger="intersect once"` inside an `x-show` panel); the drag handle still reorders. Added the global `[x-cloak]` rule to `app.css`. 5 new tests (`tests/integration/test_inline_entry_edit.py`); 151 green. Not browser-verified (Docker Desktop not running, so no Redis/worker).

- **2026-10-08 (cont.)** — LanguageChip (autonomous loop). `cv.services.language_status(cv)` returns `[{code, done, total}]` in one query (active locale first, then alphabetical); `available_languages` is now a thin wrapper over it. An entry is "done" in a language if that's its canonical language or the translation bag has a key for every translatable field with a non-empty canonical value (explicit `""` counts, matching `get_field`). New `<c-language-chip>` (filled / half / hollow dot, screen-reader text, "N of M entries translated" title); the editor shows a chip row under the top bar, and clicking a chip selects that language. Chip added to the `/components` kitchen sink. 6 new tests; 157 green.

- **2026-10-08 (cont. 2)** — Side-by-side translation editing (autonomous loop; closes the Phase 2.2 UI item). New `TranslationForm(entry, language)` builds one field per `TRANSLATABLE_FIELDS` entry (textarea for `TextField`s, `max_length` carried over) with `rows()` pairing each bound field with its canonical value. On save, blank inputs are dropped, so the field falls back to canonical; a language with nothing left is removed; and `entry.clean()` re-validates the translations shape. New `EntryTranslateView` (`entry-translate`, `/entries/<id>/translate/?lang=xx`, owner-scoped) normalises the code to lower case and rejects malformed codes or the entry's own canonical language with an inline `role="alert"` message, not a 4xx, so the HTMX swap still happens; a save fires a success toast via `HX-Trigger`. `entries/_translation_tabs.html` (one tab per existing language plus an "add language" field) is included on the entry detail page and in the editor's inline form. 10 new tests; 167 green. (The `canonical_language` UI gap noted here was closed in the next session.)

- **2026-10-08 (cont. 3)** — Original-language field on entries (autonomous loop). Every entry form now inherits `_EntryForm`, which exposes `canonical_language` as "Original language" right after the alias. It is lower-cased and must be a 2-letter code; blank keeps the current value (`en` for new entries), so existing posts that omit it don't reset it; and switching to a language that already has a translation is refused, because `get_field` would silently stop using that translation. 9 new tests (`tests/unit/test_entry_forms.py`); 176 green.

- **2026-10-08 (cont. 4)** — Settings screen (autonomous loop). `/accounts/profile/` (`profile`, previously a placeholder) is now `AccountSettingsView`: a Profile card (`ProfileForm`: display name, email, preferred language) and a Password card (Django's `PasswordChangeForm`). Each form posts its own `action` and successful saves redirect back (post/redirect/get). Email uniqueness is checked case-insensitively, because the DB constraint is case-sensitive; the preferred language is normalised (`pt_br` becomes `pt-BR`) and validated as `ll` or `ll-CC`; a password change calls `update_session_auth_hash` so the user stays logged in. The nav shows a Settings link when logged in. Django messages, enabled since Phase 1 but never rendered, are now replayed as toasts: `base.html` emits a `<template id="flash">` and `app.js` dispatches one toast per message. 8 new tests; 184 green. `preferred_language` isn't yet used as the default CV language.

- **2026-10-08 (cont. 5)** — Command palette (autonomous loop). `core.views.palette_view` (`palette`, `/palette/`, login required, GET only) returns an HTMX fragment of `[role=option]` items grouped as Actions (My CVs, New CV, New entry/section, all entries/sections, Settings), CVs (open the editor), Sections and Entries (with the entry kind as a hint). It is case-insensitive, scoped to the user's own rows, and capped at 5 per group; an empty query lists all actions plus the most recently modified CVs. `<c-command-palette>` is mounted in `base.html` for logged-in users and driven by `Alpine.data('palette')` in `app.js`: Ctrl/Cmd+K or the nav "Search" button opens it; it is a combobox with `aria-activedescendant` over a listbox; arrow keys move, Enter or click navigates, Escape or a backdrop click closes; results load debounced (150ms) via `hx-get`. 7 new tests; 191 green. All Phase 4.2 components are now done apart from the deferred Toggle/Popover/Tooltip, and Phase 4.3's screens are all built. The remaining Phase 4 items are the self-hosted fonts (manual), Lighthouse checks, and the Playwright end-to-end DoD test.

- **2026-10-08 (cont. 6)** — Phase 4 end-to-end test, first real-browser run (autonomous loop). `tests/e2e/test_happy_path.py` drives Playwright Chromium against `live_server`: signup, login, create CV info, an entry and a section, create a CV (checking that Sortable fills `#section-order`), open the editor via Ctrl+K in the command palette, edit an entry inline and see the "Saved" toast, click Render preview and wait for the PDF iframe, then download the PDF (`%PDF`, `application/pdf`); it fails on any page JavaScript error. Renders run inline by patching `_dispatch_render_job` to call `render_cv`, so no Redis or worker is needed. It skips itself when `static/dist/app.js` is missing (CI doesn't run `npm run build`, so CI is unaffected). Runtime about 16s; passed 3 out of 3 runs in a row. **Real bug it caught (fixed):** `SectionForm` silently dropped every checked entry on create and on update. Django's `save(commit=False)` sets `self.save_m2m = self._save_m2m`, which shadowed the form's own `save_m2m` override, so no `SectionEntry` rows were written. Entry syncing now lives in a `_save_m2m` override and keeps existing rows with their drag-reorder order, appending newly checked entries and deleting unchecked ones (it used to delete and recreate everything, which would have wiped the editor's ordering). 4 regression tests in `tests/unit/test_section_form.py`. 196 green. Still open for the Phase 4 DoD: Lighthouse scores, CI running the e2e test (needs `npm ci && npm run build && playwright install chromium`), and self-hosted fonts.

- **2026-10-08 (cont. 7)** — More real-browser coverage plus a palette fix (autonomous loop). Shared e2e fixtures moved to `tests/e2e/conftest.py` (`app`, `logged_in` through the real login form, `inline_renders`, `js_errors`, and a collection hook that skips the directory without the JS bundle). New `tests/e2e/test_editor_interactions.py`: (1) drag-reorder of entries and of sections via Sortable persists to the DB and survives a reload; (2) translation round trip: open an entry inline, add `es`, save the side-by-side form, see the toast and DB row, reload, the ES chip reads "1 of 4" with the partial dot, and clicking it selects ES; (3) command palette: typing and pressing Enter before the debounced results arrive now opens the fresh match. **Fix:** the palette used to open the stale, previously selected option in that case; it now marks results stale on input and defers Enter until the next swap (verified: the test fails against the old bundle and passes with the fix). 199 tests green, 3 consecutive full runs.

- **2026-10-08 (cont. 8)** — CI and image fixes found by mirroring CI locally (autonomous loop). (1) **djlint:** CI's `djlint templates --check` would have failed on 21 templates rewritten in Phase 4; ran `djlint templates --reformat` (whitespace only; long class attributes collapse onto one line) and re-ran the full suite including e2e (199 green). (2) **Docker web image shipped no CSS/JS:** `static/dist` is gitignored and the image never ran Node, so prod would have served unstyled pages with no HTMX/Alpine. Added a `node:20-bookworm-slim` `assets` stage (`npm ci`, `npm run build` with templates/apps copied in for Tailwind's content scan) whose `static/dist` is copied into the builder stage, so `collectstatic` picks it up; `static/dist` added to `.dockerignore`. (3) Dropped the standalone Typst binary download from both images (and `curl` from the web runtime), since rendercv compiles via the `typst` Python package (pinned 0.12 binary, unused). (4) **CI runs the e2e tests:** the test job now sets up Node 20, runs `npm ci && npm run build`, and `playwright install --with-deps chromium` before pytest. Locally verified: `ruff check .`, `ruff format --check .`, `djlint templates --check`, `manage.py check`, workflow YAML parses. **Not verified:** the Docker builds themselves (Docker Desktop isn't running here) and the CI run (nothing pushed); the first push will exercise both.

- **2026-10-08 (cont. 9)** — Authorization audit of the CV app (autonomous loop); these holes predate this session. **Fixed:** (1) `CVDeleteView` had no login and no ownership check, so anyone, even anonymous with a CSRF token, could delete any CV by id; it is now `LoginRequiredMixin` with an owner-scoped lookup (404 for others). (2) CVInfo/CVDesign/CVLocale/CVSettings **update** views had no login or ownership check, and `AssignUserAndAliasMixin` set `user = request.user` on save, so editing someone else's row also transferred it to you. The mixin now requires login and scopes `get_queryset` to the user (404). (3) Their create views and `CVDetailView` returned a 500 for anonymous users; they now redirect to login. (4) Removed the dead legacy routes `cv-download` (rendercv 1.x API behind a `NotImplementedError` shim) and `cv-preview` (template `cv_detail.html` doesn't exist), plus the now-unused `renderer` shim. 18 regression tests in `tests/integration/test_authorization.py`; 12 of them fail against the pre-fix views. 217 green. **Still broken (next):** dashboard *Import YAML* (`CVUploadView`) still calls the rendercv 1.x `data` API through the shim and returns a 500.

- **2026-10-08 (cont. 10)** — Import YAML ported to rendercv 2.x, plus two rendering bugs it uncovered (autonomous loop). New `apps/cv/importer.py`: `import_cv_from_yaml(user, text, alias)` validates with rendercv 2.x (`build_rendercv_dictionary_and_model`, errors flattened by the new shared `core.rendercv.format_validation_errors`, which the render task now uses too), then creates CVInfo (first email/phone/website; `tel:` prefix stripped; social networks to a dict), CVDesign (theme kept if we support it, else `classic`), the CV, and one Section plus entries per `model.cv.rendercv_sections` using rendercv's detected `entry_type`. Dates `YYYY[-MM[-DD]]` become `DateField`s (partial parts default to 1; `present` or free text becomes empty); `highlights` and `authors` lists are joined with `; ` and `, `. Every row is `full_clean`ed inside one transaction, so an over-long value gives "Could not import 'Education' entry 1: degree: ..." and nothing is saved. `CVUploadView` now has a 512 KB cap, a UTF-8 check, error toasts on the dashboard, and opens the editor with a success toast. It previously returned a 500 via the 1.x `data` shim, and the old code also reused the first `CVDesign` in the database, which could be another user's. The 1.x shim is deleted. **Rendering bugs fixed** (found by the import round trip, which renders the imported CV): `PublicationEntry.serialize` sent `authors` as a string and `TextEntry.serialize` sent `{"text": ...}`; rendercv 2.x requires a list and a bare string, so any CV with a publication or text section failed to render. Two unit tests that pinned the old shapes were updated. 12 new tests (`tests/integration/test_yaml_import.py`); 229 green. **Dead code left in place** for a deliberate cleanup: the `create_from_data_model` manager methods and `sections.services.import_sections_from_data_model` (and its tests) are no longer called.

- **2026-10-08 (cont. 11)** — Render-correctness sweep (autonomous loop). New `tests/integration/test_render_every_kind.py` renders each of the 9 entry kinds, fully populated, through real rendercv + Typst (all pass), plus every kind together in Spanish. It found two more bugs affecting every user: (1) **the editor's language picker did nothing for CVs without a CVLocale**, which includes every imported CV, because `build_render_payload` applied the override by temporarily mutating `cv.locale.language`; `CV.serialize(language=...)` now takes the override directly. (2) **Sections rendered in arbitrary order**: `CV.serialize` iterated `self.sections.all()`, and a many-to-many `.all()` ignores the through table's `order`, so dragging sections in the editor changed the database but not the PDF; it now orders by `cvsection__order`. Three of the new tests fail on the pre-fix code. Removed the dead rendercv 1.x import helpers (the four `create_from_data_model` manager methods and `sections.services.import_sections_from_data_model` with its 2 tests). 239 green.

- **2026-10-08 (cont. 12)** — **Phase 5 (API) done** (autonomous loop). New `apps/api` app mounted at `/api/v1/` (namespace `api`): read-only, owner-scoped `cvs`, `sections`, `entries` and `renders` viewsets (another user's ids return 404). Entries expose `type`, `canonical_language`, `translations` and `content` (rendercv shape); CVs expose section order, theme and per-language completeness. `POST cvs/{id}/render/` takes `{language, style}` (validated: 2-letter code, non-custom theme) and returns 202 when queued or 200 on a cache hit; `GET renders/{id}/pdf/` streams the PDF (404 until done). Auth is DRF `TokenAuthentication` plus session; the default permission is `IsAuthenticated`, with 50-per-page pagination. Settings has an "API token" card (create, regenerate, revoke; regenerating kills the old key). drf-spectacular: the public schema is at `/api/v1/schema/` and Swagger UI at `/api/v1/docs/` is staff-only; the schema validates with zero warnings. The contract snapshot `docs/api/openapi.yaml` is compared on every test run. **DoD met:** `scripts/cvmaker_cli.py` (stdlib only) does `list` and `render <id> [--language] [--style] -o out.pdf`, with polling; a test runs it against `live_server` with a token and checks the downloaded `%PDF`. New migrations come from `rest_framework.authtoken` only. 20 new tests; 259 green.

- **2026-10-08 (cont. 13)** — GDPR export and account deletion (autonomous loop; Phase 6 item). New `apps/accounts/gdpr.py`. `export_user_data(user)` returns a versioned JSON document (`format: cvmaker-export`, `version: 1`) with the account, CVs (with section order and FK ids), sections (with entry order), entries (type, canonical language, translations, every field), personal info, designs, locales, settings, and render metadata (file names only). It contains no password hash, API token or file bytes, and is served at `account-export` as an attachment. `delete_account(user)` is a hard delete: it first removes every stored file the user owns (photo, design, locale and settings files, rendered PDFs), best-effort because Django never deletes FileField files on cascade, then deletes the user inside a transaction so everything else cascades (the API token included). Settings has a "Your data" card (download) and a "Delete account" card that requires the current password plus the typed email (case-insensitive); the view logs out before deleting and redirects home with a toast. 6 new tests: export contents and exclusions, refusal paths, full deletion (rows, PDF in storage, session, token rejected by the API, other users untouched), and deletion with an already-missing file.

- **2026-10-08 (cont. 14)** — Rate limits and security headers, plus a **blank-preview bug** (autonomous loop; Phase 6 items). **Bug:** `XFrameOptionsMiddleware` sends `X-Frame-Options: DENY` everywhere, which includes the PDF response, so the editor's preview `<iframe>` would show nothing in real browsers. `render_pdf_view` is now `@xframe_options_sameorigin` (every other response stays DENY). The headless Chromium in the e2e tests has no PDF viewer, which is why the browser test hadn't caught it; it now asserts the header. **Rate limits** via `django-ratelimit` (new dependency): login 10/min per IP and 5/min per username (POST only), signup 5/hour per IP, web render 30/min per user (`group="render"`), Settings POSTs 10/min per user (password change and deletion re-check passwords). The API render action uses DRF `ScopedRateThrottle` (`render: 30/min`), because a Django-side exception inside DRF would become a 403. `core.views.ratelimited` (`RATELIMIT_VIEW`) returns 429 with `Retry-After: 60`: JSON for `/api/`, an error toast via `HX-Trigger` for HTMX, otherwise the new `templates/429.html`. Counters live in Redis in prod (`django_ratelimit.W001` silenced there with the reason); dev and test use a `ratelimit` LocMem cache with E003 silenced only there, and a test-wide autouse fixture clears the caches. **Headers:** new `core.middleware.PermissionsPolicyMiddleware` (camera, microphone, geolocation, payment and similar all `()`); HSTS, nosniff and Referrer-Policy were already set. 11 new tests in `tests/integration/test_security.py`; 276 green.

- **2026-10-08 (cont. 15)** — Waitlist flag (autonomous loop; Phase 6 item). New `SIGNUP_MODE` env setting: `open` (default) or `waitlist`; anything else raises `ImproperlyConfigured` at boot. In waitlist mode `SignUpView` serves `accounts/waitlist.html` (email only) and stores a normalised `accounts.WaitlistEntry` (migration `0002_waitlistentry`, listed in the admin). No account can be created even by POSTing the signup fields directly, and joining twice looks identical, so the form doesn't reveal who is on the list. A new `core.context_processors.site` exposes `signup_mode`, so the nav shows "Join waitlist". 8 tests; 284 green.

**Autonomous loop paused here (2026-10-08), resumed by the owner.** Everything left in Phases 6–8 needs a decision or credentials from the owner: Google/GitHub OAuth apps, an email provider (Resend or Postmark) for anymail and transactional mail, MFA, legal page content, Stripe test keys (Phase 7), and the hosting choice (Phase 8, ADR-0007). The Phase 4 leftovers also need a person: the WOFF2 fonts in `static/fonts/`, a Lighthouse run, and verifying the Docker images build. About 26 commits from this session are local and unpushed, and CI hasn't run on any of them.

- **2026-10-08 (cont. 16)** — **django-allauth migration** (the loop was resumed by the owner after the pause note above). `django-allauth[mfa]` 65.x replaces the homegrown `SignUpView`/`SignUpForm`/`LoginView` and their templates. Email is the identity: login by email, `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, unique emails, confirmation by POST only (`CONFIRM_EMAIL_ON_GET = False`, so link scanners can't confirm), and confirming the email logs you in. URL names are now `account_login`, `account_signup` and `account_logout` (POST-only); the nav, homepage and tests were updated, and `LOGIN_URL = "account_login"`. **Look and feel:** instead of overriding each allauth page, `templates/allauth/layouts/{base,entrance,manage}.html` and all 22 `templates/allauth/elements/*.html` are restyled with the design system (buttons map allauth's `tags` to our variants), so login, signup, reset, email, 2FA and connections all render as our cards. `base.html` gained an outer `{% block main %}` so layouts can wrap the page's `content`. Checked visually in Chromium. **Flows kept:** waitlist mode now goes through `accounts.adapter.AccountAdapter.is_open_for_signup`; allauth renders `account/signup_closed.html` (our waitlist form, posting to the new `waitlist` URL). Settings links to allauth's email management and 2FA; email was removed from `ProfileForm`, so changes always go through verification. The data export includes allauth email addresses. **Rate limits:** allauth's `ACCOUNT_RATE_LIMITS` (failed logins 10/min per IP and 5 per 5 min per account, signup 5/hour per IP, password reset, confirmation emails) replace the django-ratelimit decorators on the old views (render/settings limits unchanged). **MFA:** TOTP and recovery codes (`MFA_TOTP_ISSUER = "CVMaker"`). **Social:** Google/GitHub providers append themselves to `INSTALLED_APPS` only when their client id/secret env vars are set. **Data migration** `accounts/0003` gives every existing user a verified primary `EmailAddress`, so mandatory verification doesn't lock them out. Also fixed migration drift: `rendering/0002` renames the index the hand-written Phase 3 migration had named differently, and CI now runs `makemigrations --check`. Tests: `test_auth_flow.py` rewritten (signup to mail to POST-confirm to logged in, unverified login refused, case-insensitive email login, reset link works, POST-only logout, entrance pages styled, 2FA page, account locked after 5 failures, signup limit); waitlist and settings tests adapted; the e2e happy path now signs up, opens the emailed link and confirms in Chromium. 291 green.

- **2026-10-08 (cont. 17)** — Email (Phase 6, owner-resumed loop). **Provider selection:** `EMAIL_PROVIDER` = `console` (default) / `smtp` / `resend` / `postmark` maps to the Django or anymail backend (`django-anymail` 13 added, `anymail` installed); an unknown value raises `ImproperlyConfigured`. `DJANGO_EMAIL_BACKEND` stays as an escape hatch (empty counts as unset). `prod.py` refuses to boot with `console`, or with resend/postmark and no `RESEND_API_KEY`/`POSTMARK_SERVER_TOKEN`. New `SITE_URL` for absolute links from the worker; `.env.example` documents all of it. **Branding:** `templates/email/base.html` is a table-based layout with inline styles for email clients. allauth's signup and normal confirmation and password-reset emails get CVMaker subjects, text bodies (replacing allauth's "Hello from <host>") and HTML versions with a button. `core.email.send_templated_email(to, prefix, ctx)` sends multipart mail for our own emails. **Welcome email** on a user's first confirmed address (`accounts.signals`, allauth `email_confirmed`), not on later email changes. **Render notifications:** new opt-in `User.notify_on_render` (migration `accounts/0004`, a checkbox in Settings). `render_cv` emails the requester on done (PDF and editor links), on handled failure and on unexpected crash (with the error); sending is wrapped so an email failure can never fail a render. Not done: the weekly digest (needs a scheduler, Phase 8). 13 tests in `tests/integration/test_email.py`; 304 green.

- **2026-10-08 (cont. 18)** — Local demo tooling. `manage.py seed_demo` creates (or resets, via `delete_account`) `demo@cvmaker.test` / `demo-password-123` with a verified email and a CV that has EN content, ES translations on 4 of 6 entries and a started-but-incomplete FR, so chips, side-by-side translation, reorder and render all have data. `RENDER_INLINE` (dev only, defaults to on when `REDIS_URL` is unset; `prod.py` refuses to boot with it) makes `_dispatch_render_job` run `render_cv` inside the request, so `runserver` alone is enough to see PDFs. The Django debug toolbar is now opt-in (`DEBUG_TOOLBAR=1`): its handle covered the right edge of every page and blocked clicks on the real UI (found by driving the live server with Playwright). Walked the running server end to end in Chromium (login, dashboard, editor, Spanish ModernCV render, inline translation panel, palette, settings, schema) with no JS errors and no server tracebacks; the rendered PDF was rasterised and checked (ES where translated, EN fallback elsewhere). README gained the new quick start and a "What to try" table. 4 tests; 308 green.

- **2026-10-12** — Build a CV from the editor (owner feedback: "where can I add my sections? the workflow is confusing"). **Cause:** the model is entries, then sections that group them, then CVs that list sections, but the only way to create a section was the standalone `/section/create/` page, and nothing in the editor pointed to it (the empty state linked to the CV settings form). **Fix:** the editor now has **+ Add section** (`/section/create/?cv=<id>`: the new section is attached to that CV and you return to the editor), **Use an existing section** (CV settings), and **+ New entry** inside every section (`/entry/create/?section=<id>&cv=<id>`: the entry is appended to that section and you return to the editor). A section that already holds entries fixes the kind (rendercv allows one per section): the kind picker is skipped, and a tampered POST of another kind is refused with an error. The context ids are looked up through the user's own rows (a bad, foreign or non-UUID id is ignored), and the editor URL is built server-side, not taken from the query (no open redirect). New `sections.services` helpers `attach_section_to_cv`, `append_entry_to_section` and `section_entry_kind`. The empty-state text now explains what a section is; the entry-create page explains entries, sections and CVs; the nav shows **Sections** and **Entries** for signed-in users. **Bug found by the new browser test:** server-side messages never appeared as toasts. `app.js` looked for them with `querySelectorAll` inside a `<template>`, whose children live in `.content`, so the Phase 6 "flash messages as toasts" work did nothing in a real browser (my earlier test only checked the HTML). Fixed; the browser test now asserts the toast. 17 integration tests and 1 e2e test (empty CV, add section, add entry, kind lock, render); 326 green. **Process note:** I briefly ran `djlint --reformat` over `apps/`, which rewrote unrelated app templates; I reverted everything except the files I meant to change. Note that CI's djlint check covers `templates/` only.

- **2026-10-12 (cont.)** — Quick-start flow (continuing the workflow fixes). **Problem:** `+ New CV` opened the full CV form, which required choosing personal info, locale, settings and design records that a new user doesn't have, with links out to four other setup pages. **Now:** `+ New CV` (dashboard, homepage and palette) goes to `cv/new/`, a one-field "Name your CV" page. `create_starter_cv` creates the CV with a personal-details record pre-filled from the account (display name, email) and the classic design, then opens the editor. The editor has a **Personal details** card that stays collapsed when a name is present and opens itself while the name is empty. It lazy-loads an HTMX form (`cv-info-inline`: name, email, phone, location, website) that saves in place, fires a toast, refreshes the card's summary line out of band, creates and attaches a record if the CV has none, and 404s for other users. The old full form (`cv-create`) still exists but is no longer linked. 14 integration tests and an e2e test (dashboard, New CV, details, section, entry, render); 341 green.

- **2026-10-12 (cont. 2)** — Help and Import pages. The nav's Templates, Import and Help links all led to "coming soon" placeholders, which looked unfinished and did nothing for the workflow confusion. **Help** is now a real guide (`templates/help.html`): entries, sections and CVs as the three building blocks, a five-step quick start, the editor's features (reorder, inline edit, translations, chips, palette), one-kind-per-section, import, data export, API. **Import** is a real page (`templates/import.html`): explains the rendercv YAML import (512 KB, nothing saved on error), shows the upload form for signed-in users and a log-in prompt (with `next`) otherwise. **Templates** is removed from the nav until there is a real gallery; its route stays. 6 tests; the smoke tests still pass.

- **2026-10-12 (cont. 3)** — Dashboard polish found by looking at the live pages. The dashboard's orange ↓ ("Render PDF") and the CV detail page's "Render PDF" button POSTed straight to `rendering:enqueue`; for a non-HTMX request that returns a bare HTML fragment, so users landed on an unstyled snippet. Both are now links to `cv-editor?render=1`; the editor starts rendering as soon as it loads when that flag is present (`hx-trigger="submit, load"` on the top-bar form), and shows the preview. The enqueue endpoint itself is unchanged (API/tests rely on it). The icon-button `danger` variant is now a quiet text-coloured ghost instead of a solid red block (the solid style stays on confirmation buttons). 4 tests (3 integration, 1 e2e); 351 green.

- **2026-10-12 (cont. 4)** — Library pages. Sections and Entries leaked class names ("ExperienceEntry", "ONELINEENTRY"). New `kind_label` filter ("One line", "Reversed numbered") is used on the sections list and detail chips and on the entry list and detail headers. The entry list also says how each entry is used ("used in 2 sections" or "not in any section yet", via a `Count` annotation), so orphaned entries are easy to spot. 8 tests; 359 green.

### 2026-10-12 (cont. 5) — Health probes
- `/healthz` (liveness) and `/readyz` (DB check, 503 when down); exempt from the prod HTTPS redirect. Tests in `tests/integration/test_health.py`.
- Production logs are now valid JSON (`cvmaker.logging_utils.JsonFormatter`, tracebacks included); optional Sentry via `SENTRY_DSN` (install `sentry-sdk` first).

### 2026-10-12 (cont. 6) — Templates gallery
- `/templates/` is a public gallery: each style rendered from a sample CV (`core/gallery.py`, cached 24h) with "Use this style" → `/cv/new/?style=…`; quick-start form gained a Style select. Nav links Templates again.
- Real `/status/` (web + database, 503 when DB down) and `/about/` pages. Contact stays a placeholder (needs the owner's address).
- Dashboard "Duplicate" on each CV (`cv-duplicate`, POST, owner-scoped; uses `clone_cv`, sections shared).

### 2026-10-12 (cont. 7) — Render history and share links
- `ShareLink` model (migration 0003): unguessable token, 1/7/30-day expiry, revoke, view counter. `/renders/cv/<id>/history/` lists past renders with Open/Share; public `/s/<token>/` serves the PDF (noindex, no-store; 404 when expired/revoked). Editor has a "History & sharing" button.

### 2026-10-12 (cont. 8) — Public profile pages
- Opt-in `/@handle/` page rendering a chosen CV as HTML (`accounts/public.py`). New user fields `public_handle` (unique, NULL = private), `public_cv`, `public_show_contact` (default off: email/phone hidden); set in Settings with ownership/format validation. Included in the GDPR export. Includes OG tags and JSON-LD.

### 2026-10-12 (cont. 9)
- `manage.py prune_data [--render-days 90] [--link-grace-days 30] [--dry-run]`: removes long-expired/revoked share links and old renders (keeps each CV's newest finished render and anything with a live share link). Needs a scheduler to run it (owner/hosting).
- Entries page: search by name (`?q=`) and "Not in any section" filter (`?unused=1`).
- Dashboard cards link the latest finished PDF and the render history. `/robots.txt` (blocks app/API/share paths) and `/sitemap.xml` (static pages + published profiles).
