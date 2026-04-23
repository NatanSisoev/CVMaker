# Phase 1 handoff

All of Phase 1 (sub-phases 1.1 – 1.6) is staged in the repo. One PowerShell
script applies every git operation, app move, and DB reset locally.

## What's already in the repo

**Phase 1.1 — layout + uv**
- `pyproject.toml` + uv-managed deps (dev group has ruff, mypy, pytest, etc.)
- `src/cvmaker/` project package with split settings (`base/dev/prod/test`)
- `src/cvmaker/{urls,wsgi,asgi}.py` wired to the split settings
- `manage.py` at repo root (points `DJANGO_SETTINGS_MODULE` at `cvmaker.settings.dev`)
- `apps/core/` with `TimestampedModel`, `UUIDModel`, `UUIDTimestampedModel`

**Phase 1.2 — dev tooling**
- `.pre-commit-config.yaml` (ruff + djlint + django-upgrade + mypy)
- `Makefile` (dev/test/lint/fmt/typecheck/ci/up/down, every target via `uv run`)
- `.editorconfig`

**Phase 1.3 — docker**
- `docker/web.Dockerfile` + `docker/worker.Dockerfile` (multi-stage, Typst baked in)
- `docker/entrypoint.sh` (wait-for-db, opt-in migrations, prod collectstatic)
- `compose.yaml` (web + worker + postgres 16 + redis 7 + minio)
- `.dockerignore`

**Phase 1.4 — CI**
- `.github/workflows/ci.yml` — lint / typecheck / test against Postgres
  service container / docker build with GHA cache

**Phase 1.5 — custom User**
- `cvmaker/accounts/models.py` rewritten with custom `User(AbstractUser)` +
  `UserManager` (email identifier, `display_name`, `preferred_language`)
- `cvmaker/accounts/{forms,views,admin}.py` migrated to `get_user_model()` /
  `UserAdmin` subclass
- Every `FK(User, ...)` in `cv/entries/sections` rewritten to
  `FK(settings.AUTH_USER_MODEL, ...)`

**Phase 1.6 — tests**
- `tests/{unit,integration,e2e}/` tree
- `tests/factories.py` (UserFactory, CVFactory, SectionFactory, every Entry subtype)
- `tests/conftest.py` (user, admin_client, cv, section, entry fixtures)
- Unit tests for the User model and entry `serialize()` contracts
- Integration smoke tests (URL reversal, signup + login, admin, public stubs)

**ADRs**
- `docs/adr/0001-project-structure.md`
- `docs/adr/0004-custom-user-model.md`

## What you need to do

One script, one run, from the repo root on your Windows machine.

```powershell
cd C:\Users\natan\CVMaker
.\scripts\phase1_migrate.ps1
```

The script is verbose and fails loudly. It will:

1. Preflight — clean tree on `main`, `.env` present, `python`/`psql` on PATH.
2. Install `uv` if you don't have it (Astral's official installer).
3. `git mv cvmaker/{accounts,cv,entries,sections}` → `apps/`.
4. `git mv cvmaker/{templates,static,media}` → repo root.
5. `git rm -rf cvmaker/cvmaker` and `git rm cvmaker/manage.py` (old package).
6. Delete every `0*_*.py` migration under `apps/` (all reference `auth.User`,
   being replaced).
7. Remove the now-empty `cvmaker/` directory.
8. `uv sync` — resolve from `pyproject.toml`, populate `.venv/`.
9. `dropdb cvmaker` + `createdb cvmaker` — clean slate for the custom User.
10. `uv run python manage.py makemigrations accounts core cv entries sections`.
11. `uv run python manage.py migrate`.
12. `uv run python manage.py check` — must be green.
13. `git add -A`, show `git status --short`, wait for you to press Enter,
    then commit with a full Phase 1.1 + 1.5 message.

If anything fails the script exits with a red `[FAIL]` line and tells you
what went wrong. Safe to re-run only if it died before the final commit.

## After the script commits

```powershell
git log --stat -1              # eyeball the diff
git push origin main
uv run pre-commit install      # install the git hooks
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Hit <http://localhost:8000>, log into `/admin/` with the superuser, confirm
the site still renders.

Then run the local gate once to smoke-test the tooling end-to-end:

```powershell
uv run pytest                  # should be green
uv run ruff check .            # zero warnings expected
uv run ruff format --check .   # no formatting diffs
```

First push to GitHub triggers CI (`.github/workflows/ci.yml`) — lint,
typecheck, test against a real Postgres service container, and a docker build.
Enable branch protection on `main` after the first green run so the gate
is enforced on every PR.

## Known leftovers

- `_test_perm` — empty file I dropped during a sandbox permission probe. Safe
  to delete: `Remove-Item .\_test_perm`.
- `requirements.txt` — kept as a fallback until CI is uv-first (Phase 1.4).
  Regenerate with `uv export --no-hashes > requirements.txt` when deps change.

## What's next

Phase 1 closes when CI goes green and branch protection is on. After that:

- Phase 2.1 — replace the `GenericForeignKey` on `SectionEntry` with a real FK
  to `BaseEntry`, drop the project-wide `pre_delete` signal. Write ADR-0005.
- Phase 2.2 — per-entry translations (`canonical_language` +
  `translations` JSONField, with `entry.serialize(language="es")` doing the
  merge). Write ADR-0006.
- Phase 2.3 — move logic out of views into per-app `services.py` modules.
- Phase 2.4 — `CVInfo.save()` → `.clean()`, drop `default=1` on `CV.user`,
  tidy imports.

`ROADMAP.md` has the authoritative checklist; each item is small enough to
fit in one session.
