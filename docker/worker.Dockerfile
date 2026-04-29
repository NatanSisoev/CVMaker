# Worker image — shares the web build artifacts; the CMD is the only diff.
#
# Keep this file almost identical to web.Dockerfile so the two images stay in
# sync. The web image already contains Typst, rendercv deps, and the project.
# The worker reuses all of that and runs an RQ worker (Phase 3) instead of
# gunicorn.

FROM python:3.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

# ----------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ARG TYPST_VERSION=0.12.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE=cvmaker.settings.prod

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
        fontconfig \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
    | tar -xJ -C /tmp \
    && mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
    && rm -rf /tmp/typst-x86_64-unknown-linux-musl

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app

USER app

# Phase 3.3: consume the "render" queue. ``django_rq`` reads RQ_QUEUES
# from Django settings and connects with the configured Redis URL.
# A single worker per container -- compose can scale with `--scale worker=N`.
CMD ["python", "manage.py", "rqworker", "render"]
