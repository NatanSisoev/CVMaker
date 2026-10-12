"""Logging helpers: a dependency-free JSON formatter for log aggregators."""

from __future__ import annotations

import json
import logging


class JsonFormatter(logging.Formatter):
    """One valid JSON object per line, including the traceback when present."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
