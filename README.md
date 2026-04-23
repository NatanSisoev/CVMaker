# CVMaker

A Django web app for composing CVs from reusable, per-user building blocks —
your entries, your sections, your info — and rendering them to PDF via Typst.
The product vision: write each experience once, translate it to the languages
you care about, then assemble the right CV for each role at the click of a
button.

> **Status:** active refactor. See [`ROADMAP.md`](ROADMAP.md) for the plan,
> [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for what exists today,
> [`docs/DESIGN.md`](docs/DESIGN.md) for the design direction, and
> [`docs/adr/`](docs/adr/) for the architectural decisions.

## Quick start

Prerequisites: **Python 3.12+**, **PostgreSQL 14+**, and [**uv**](https://docs.astral.sh/uv/).

```bash
# 1. Clone
git clone https://github.com/NatanSisoev/CVMaker.git
cd CVMaker

# 2. Install uv (once per machine)
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 3. Dependencies + venv (uv does both from pyproject.toml/uv.lock)
uv sync

# 4. Environment
cp .env.example .env        # macOS / Linux
# Copy-Item .env.example .env    # Windows
# Open .env and set DJANGO_SECRET_KEY and DB_* to match your Postgres.
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 5. Database
createdb cvmaker            # or whatever DB_NAME you set
uv run python manage.py migrate
uv run python manage.py createsuperuser   # optional, for /admin

# 6. Run
uv run python manage.py runserver
```

Visit <http://localhost:8000>.

## Layout

```
CVMaker/
├── manage.py                   # entrypoint; DJANGO_SETTINGS_MODULE=cvmaker.settings.dev
├── pyproject.toml              # deps + tool config (ruff, mypy, pytest, coverage)
├── uv.lock                     # locked resolver output
├── src/
│   └── cvmaker/                # project package
│       ├── settings/           # base / dev / prod / test
│       ├── urls.py
│       ├── wsgi.py             # prod default
│       └── asgi.py             # prod default
├── apps/                       # domain apps (on sys.path for short imports)
│   ├── core/                   # shared abstract models + mixins
│   ├── accounts/               # custom User
│   ├── cv/                     # CV aggregate + Info / Design / Locale / Settings
│   ├── sections/               # ordered collections of entries
│   └── entries/                # polymorphic entry types
├── templates/
├── static/
├── media/                      # user uploads (gitignored)
├── tests/
├── docs/                       # design, audit, ADRs
│   └── adr/                    # architecture decision records
├── scripts/                    # one-off maintenance scripts
└── ROADMAP.md                  # the plan
```

Why `src/` + `apps/`? See [`docs/adr/0001-project-structure.md`](docs/adr/0001-project-structure.md).
Why a custom User model? See [`docs/adr/0004-custom-user-model.md`](docs/adr/0004-custom-user-model.md).

## Common tasks

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py shell_plus          # via django-extensions (dev only)
uv run pytest                               # all tests
uv run pytest -k smoke                      # one set
uv run ruff check .                         # lint
uv run ruff format .                        # format
uv run mypy src apps                        # type check
```

All dev tools live in `pyproject.toml` under `[dependency-groups].dev` and
`[tool.*]` sections — one source of truth for CI, pre-commit, and your editor.

## Environments

`DJANGO_SETTINGS_MODULE` is wired per entrypoint:

- `manage.py` defaults to `cvmaker.settings.dev` (DEBUG=True, local DB,
  debug-toolbar, console email).
- `wsgi.py` / `asgi.py` default to `cvmaker.settings.prod` (DEBUG=False,
  HSTS, structured logs, Redis cache).
- `pytest` pins `cvmaker.settings.test` (SQLite in-memory, migrations skipped,
  MD5 password hasher for speed).

Override with `DJANGO_SETTINGS_MODULE=cvmaker.settings.prod uv run python manage.py <cmd>`.

## Development notes

- **PDF rendering** happens in the request thread today. Phase 3 moves it to a
  queue — don't be surprised if downloads stall on cold starts.
- **Frontend** is still Bootstrap 5 + crispy-forms. Phase 4 replaces it with
  Tailwind + HTMX + Alpine; see `docs/DESIGN.md`.
- **`requirements.txt`** is a fallback for people without uv. Regenerate with
  `uv export --no-hashes > requirements.txt` when deps change.

## Contributing to yourself

Every session, pick the next unchecked item in `ROADMAP.md`, do the work, tick
the box, and append a dated line to the roadmap's "Session log" section.
