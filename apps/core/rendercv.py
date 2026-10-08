"""Small shared helpers around the rendercv 2.x API."""

from __future__ import annotations


def format_validation_errors(exc, heading: str) -> str:
    """Flatten a ``RenderCVUserValidationError`` into one readable string.

    Each problem becomes ``"path -> to -> field: message"`` (or just the
    message when rendercv gives no location), under ``heading``.
    """
    lines = []
    for err in exc.validation_errors:
        where = " -> ".join(str(part) for part in (err.schema_location or ()))
        lines.append(f"{where}: {err.message}" if where else err.message)
    return heading + "\n" + "\n".join(lines)
