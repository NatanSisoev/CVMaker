import json
import logging

from cvmaker.logging_utils import JsonFormatter


def _record(msg, exc_info=None):
    return logging.LogRecord("cv", logging.WARNING, __file__, 1, msg, None, exc_info)


def test_output_is_valid_json_even_with_quotes():
    out = json.loads(JsonFormatter().format(_record('he said "hi"\nnewline')))
    assert out["msg"] == 'he said "hi"\nnewline' and out["level"] == "WARNING"


def test_traceback_is_included():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        out = json.loads(JsonFormatter().format(_record("failed", sys.exc_info())))
    assert "ValueError: boom" in out["exc"]
