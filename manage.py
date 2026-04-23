#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    """Run administrative tasks."""
    repo_root = Path(__file__).resolve().parent

    # Make `cvmaker` (settings/urls/etc.) and the domain apps importable.
    for extra_path in (repo_root / "src", repo_root / "apps"):
        p = str(extra_path)
        if p not in sys.path:
            sys.path.insert(0, p)

    # Default to dev; override with DJANGO_SETTINGS_MODULE=cvmaker.settings.prod
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cvmaker.settings.dev")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed and available on your "
            "PYTHONPATH? Did you forget to activate the virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
