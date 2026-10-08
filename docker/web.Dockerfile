# Multi-stage build for the Django web service.
#
# Stage 0 — assets: Node builds static/dist (Tailwind CSS + HTMX/Alpine/Sortable
#           bundle). static/dist is gitignored, so the image must build it.
# Stage 1 — builder: install uv, sync deps into /app/.venv.
# Stage 2 — runtime: slim Python + fonts, copy venv, non-root user.
#
# Typst compiles in-process via the `typst` Python package that rendercv[full]
# pulls in, so no standalone Typst binary is installed.

# ----------------------------------------------------------------------
# Stage 0 — assets
# ----------------------------------------------------------------------
FROM node:20-bookworm-slim AS assets

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Tailwind scans templates and apps for class names (see tailwind.config.js).
COPY tailwind.config.js postcss.config.js ./
COPY static/src ./static/src
COPY templates ./templates
COPY apps ./apps
RUN npm run build

# ----------------------------------------------------------------------
# Stage 1 — builder
# ----------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build deps for psycopg + any C extensions. Removed in the runtime stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# uv from Astral's official image (pinned).
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dep manifests first for a cache-friendly layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the project and sync the remainder.
COPY . .
RUN uv sync --frozen --no-dev

# Built front-end assets from stage 0 (collectstatic picks them up at boot).
COPY --from=assets /app/static/dist ./static/dist

# ----------------------------------------------------------------------
# Stage 2 — runtime
# ----------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE=cvmaker.settings.prod

# Runtime-only deps: libpq for psycopg, fontconfig + fonts for Typst rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        fontconfig \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

# Copy venv + project from the builder.
COPY --from=builder --chown=app:app /app /app

# Entrypoint handles `wait-for-db` and `migrate` before starting gunicorn.
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "cvmaker.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
