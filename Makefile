# CVMaker — developer Makefile.
#
# All commands go through `uv run` so they pick up pyproject.toml's deps
# and pinned Python version. The dev settings file is the default entrypoint;
# override with DJANGO_SETTINGS_MODULE=cvmaker.settings.prod make <target>.
#
# On Windows, run these targets via `make` from Git Bash / WSL, or copy the
# underlying command. (We could ship a psake script if anyone actually needs
# native Windows make; for now uv + python calls work cross-platform.)

.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
.ONESHELL:
.SILENT:

PY := uv run python
MANAGE := $(PY) manage.py

## -------- meta --------
help:  ## Show this help
	awk 'BEGIN {FS = ":.*##"; printf "\nUsage: make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

## -------- setup --------
install:  ## uv sync all deps + install pre-commit hooks
	uv sync
	uv run pre-commit install

## -------- development --------
dev:  ## Run the dev server on :8000
	$(MANAGE) runserver

shell:  ## Django shell (with shell_plus if available)
	$(MANAGE) shell_plus 2>/dev/null || $(MANAGE) shell

migrate:  ## Apply migrations
	$(MANAGE) migrate

migrations:  ## Make migrations (use app=<name> to narrow)
	$(MANAGE) makemigrations $(app)

superuser:  ## Create an admin user
	$(MANAGE) createsuperuser

## -------- quality gates --------
lint:  ## Ruff lint + djlint templates
	uv run ruff check .
	uv run djlint templates --check

fmt:  ## Ruff format + djlint reformat
	uv run ruff format .
	uv run ruff check . --fix
	uv run djlint templates --reformat

typecheck:  ## mypy over src + apps
	uv run mypy src apps

test:  ## pytest with coverage
	DJANGO_SETTINGS_MODULE=cvmaker.settings.test uv run pytest

test-fast:  ## pytest, fail on first failure, no coverage
	DJANGO_SETTINGS_MODULE=cvmaker.settings.test uv run pytest -x --no-cov

ci:  ## Run the full gate locally (mirrors .github/workflows/ci.yml)
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

## -------- docker --------
up:  ## docker compose up (web + worker + postgres + redis + minio)
	docker compose up --build

down:  ## docker compose down + remove volumes
	docker compose down -v

## -------- housekeeping --------
clean:  ## Remove caches and build artifacts
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache \) -prune -exec rm -rf {} +
	rm -rf .coverage htmlcov dist build *.egg-info

lock:  ## Regenerate uv.lock and requirements.txt fallback
	uv lock
	uv export --no-hashes --no-dev > requirements.txt

.PHONY: help install dev shell migrate migrations superuser lint fmt typecheck test test-fast ci up down clean lock
