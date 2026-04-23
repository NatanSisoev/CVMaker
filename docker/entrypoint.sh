#!/usr/bin/env bash
# Container entrypoint for the web service.
#
# Order of operations:
#   1. Wait for Postgres to accept connections (loops with timeout).
#   2. Apply migrations (only when RUN_MIGRATIONS=1, default off; CI flips it
#      on for one-shot jobs, prod does it via a release step).
#   3. Collect static (prod only; dev serves direct from disk).
#   4. Exec whatever CMD the image was started with.
#
# Set -euo pipefail so any unhandled error aborts the container instead of
# silently masking a broken startup.

set -euo pipefail

# --------------------------------------------------------------------
# wait-for-db
# --------------------------------------------------------------------
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"

echo "entrypoint: waiting up to ${DB_WAIT_TIMEOUT}s for ${DB_HOST}:${DB_PORT}..."
for ((i = 0; i < DB_WAIT_TIMEOUT; i++)); do
    if python -c "
import socket, sys
try:
    socket.create_connection(('${DB_HOST}', ${DB_PORT}), timeout=1).close()
except OSError:
    sys.exit(1)
"; then
        echo "entrypoint: database is up"
        break
    fi
    sleep 1
done

# --------------------------------------------------------------------
# migrations (opt-in)
# --------------------------------------------------------------------
if [[ "${RUN_MIGRATIONS:-0}" == "1" ]]; then
    echo "entrypoint: applying migrations..."
    python manage.py migrate --noinput
fi

# --------------------------------------------------------------------
# collectstatic (prod only; dev serves from STATICFILES_DIRS)
# --------------------------------------------------------------------
if [[ "${DJANGO_SETTINGS_MODULE:-}" == "cvmaker.settings.prod" ]]; then
    echo "entrypoint: collecting static files..."
    python manage.py collectstatic --noinput
fi

# --------------------------------------------------------------------
# handoff
# --------------------------------------------------------------------
echo "entrypoint: exec -- $*"
exec "$@"
