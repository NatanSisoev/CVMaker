"""
Settings package.

Do not import from this module directly — it intentionally has no `default`
export. Select an environment by setting ``DJANGO_SETTINGS_MODULE``:

    cvmaker.settings.dev      # local development (DEBUG=True, Postgres)
    cvmaker.settings.prod     # production (DEBUG=False, S3, HSTS, etc.)
    cvmaker.settings.test     # pytest runs (in-memory SQLite, no migrations)

``manage.py`` defaults to ``cvmaker.settings.dev`` if the variable is unset.
"""
