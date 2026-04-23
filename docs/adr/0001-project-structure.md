# ADR-0001: Project structure, dependency management, and settings split

- **Status:** accepted
- **Date:** 2026-04-22
- **Phase:** 1.1

## Context

At the end of Phase 0 the repository had the shape of a freshly-run
`django-admin startproject`: a single nested `cvmaker/cvmaker/` directory with
everything (settings, apps, templates, static) one level deep inside a
top-level `cvmaker/` folder, a flat `requirements.txt` with no lockfile, and a
single 180-line `settings.py` that mixed dev, prod, and test concerns behind
runtime `if not DEBUG` branches.

This shape works for a prototype but scales badly:

- **No lockfile.** A fresh checkout a year from now resolves to whatever pip
  feels like that day. Irreproducible builds are CI fragility.
- **Single settings file.** Mixing dev + prod + test logic inside
  `if not DEBUG:` gates means every environment has to know about every other
  environment, and a wrong `DEBUG` default leaks dev behaviour to production.
- **Nested `cvmaker/cvmaker/`.** The double-nested layout makes imports
  confusing (`cvmaker.cvmaker.settings`?), makes the project root ambiguous,
  and puts apps, settings, and templates at the same depth — which invites the
  "just dump it at the top level" reflex for anything new.
- **No `pyproject.toml`.** Tooling config (ruff, mypy, pytest, djlint, coverage)
  ends up in 6+ dotfiles. `pyproject.toml` is the modern convention and the
  single-source-of-truth for everything tool-related.

Phase 1 is the window where we can rip this band-aid off and never touch
layout again. By Phase 2 we'll be writing feature code and a reshuffle would
be disruptive.

## Decision

### Layout — `src/` + `apps/`

```
CVMaker/
├── manage.py                    # entrypoint
├── pyproject.toml               # deps, tooling config
├── uv.lock                      # locked resolver output
├── src/
│   └── cvmaker/                 # project package (settings, urls, wsgi, asgi)
│       ├── settings/            # base / dev / prod / test
│       ├── urls.py
│       ├── wsgi.py
│       └── asgi.py
├── apps/                        # domain apps, one directory each
│   ├── core/                    # shared mixins / base models
│   ├── accounts/                # custom User
│   ├── cv/                      # CV aggregate
│   ├── sections/
│   ├── entries/
│   └── rendering/               # Phase 3
├── templates/                   # project-wide templates
├── static/                      # static sources + build output
├── tests/                       # unit / integration / e2e
├── docker/                      # Dockerfiles + entrypoints
└── docs/
```

The `src/` layout ([PEP 517/518](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/))
enforces that code runs against the installed package, not the working
directory — preventing "works in dev, fails in CI" bugs where local imports
accidentally masked missing dependencies.

`apps/` as a sibling to `src/` keeps the domain apps physically separate from
the plumbing (settings, urls, wsgi). Adding `apps/` to `sys.path` in
`manage.py` and `settings/base.py` means apps are importable by their short
names — `accounts`, `cv`, `entries` — so every `from accounts.models import X`
in the existing code keeps working without a rewrite.

### Dependency management — `uv`

Using [uv](https://docs.astral.sh/uv/) rather than pip/poetry/pipenv/hatch:

- Fast (Rust-based resolver; ~10x pip).
- Generates an accurate `uv.lock` that pins the full resolution graph, so
  every clone gets byte-identical dependencies.
- `pyproject.toml`-native; no vendor-specific syntax in the project file.
- First-class dependency groups (`[dependency-groups] dev = [...]`) — no
  separate `requirements-dev.txt` to drift.

`requirements.txt` is kept as a fallback for people who haven't installed uv
yet, regenerated from `uv export --no-hashes > requirements.txt`. Once CI and
the README are uv-first (Phase 1.4) we can drop it.

### Settings — split per environment

```
settings/
├── base.py     # everything shared; always loaded
├── dev.py      # DEBUG=True, local DB, debug-toolbar, console email
├── prod.py     # DEBUG=False, HSTS, S3, Redis, structured logs
└── test.py     # SQLite in-memory, MIGRATION_MODULES disabled, MD5 hasher
```

Each env-specific file starts with `from .base import *` and overrides. This
eliminates the `if not DEBUG:` branches in `base.py` and makes the test
suite an order of magnitude faster (no disk I/O for migrations; in-memory
SQLite).

`DJANGO_SETTINGS_MODULE` selects the file: `manage.py` defaults to
`cvmaker.settings.dev`, `wsgi.py` and `asgi.py` default to
`cvmaker.settings.prod`, `pytest` pins `cvmaker.settings.test`.

### Tooling config — all in `pyproject.toml`

- **ruff** — lint + format (replaces black, isort, flake8, pyupgrade)
- **djlint** — Django template lint
- **mypy** — type checks with django-stubs
- **pytest** — `DJANGO_SETTINGS_MODULE = cvmaker.settings.test`, strict markers
- **coverage** — branch coverage, exclude migrations

Editor integration is via LSPs, so the same config governs IDEs, CI, and
pre-commit. One source of truth.

## Consequences

### Positive

- Reproducible builds (lockfile + pinned deps + single settings per env).
- Import paths are unambiguous; new apps go in `apps/<name>/` with no thinking.
- Test suite is fast enough to run on save (in-memory SQLite).
- Configuration debt is paid down once; future env changes are small diffs.
- The layout matches industry standards, which matters for onboarding.

### Negative / trade-offs

- The Phase 1 migration is disruptive: 60+ files move, all migrations are
  regenerated, the dev DB must be recreated. This is paid once, in a single
  scripted step, with no real data at risk.
- uv is Astral's project and only ~1 year old. Maintenance-risk is low but
  non-zero. Mitigation: `pyproject.toml` is standards-based, so swapping uv
  out for poetry/pdm/hatch is a tooling change not a project change.
- `sys.path` manipulation in `settings/base.py` and `manage.py` is a minor
  smell. The alternative — renaming every `from accounts.X` to
  `from apps.accounts.X` — is a much bigger diff and would need to happen
  *every time* we move an app. The tradeoff favours the smell.

## Alternatives considered

- **Keep flat `cvmaker/<app>` layout.** Cheap today, expensive every time
  we add a new concern. Rejected: we're pre-launch and this is the window.
- **Poetry.** Mature, but slower to resolve, the lockfile format is
  non-standard, and it conflates dependency management with virtualenv
  management. uv does less and does it faster.
- **Hatch.** Excellent, but designed for library authors (it leans into
  package building). We're shipping a Django app, not a PyPI package.
- **Monorepo with workspaces.** Overkill for one application.

## References

- [src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Two Scoops of Django settings pattern](https://www.feldroy.com/books/two-scoops-of-django-3-x)
- [uv docs](https://docs.astral.sh/uv/)
