"""
One-shot Phase 1 stopgap: rewrite rendercv 1.x imports to something that
at least *loads* under rendercv 2.x.

Background
----------
The code in ``apps/cv/`` was written against rendercv 1.x. Two things broke
when we pinned rendercv>=2.2:

1.  ``rendercv.data`` was removed outright. Callers used to:
        from rendercv.data import read_a_yaml_file
        from rendercv.data.models.curriculum_vitae import available_social_networks
        from rendercv import data
    None of these resolve in 2.x.
2.  ``read_a_yaml_file`` was deleted entirely (2.x wants YAML *text*, not a
    path).
3.  ``available_social_networks`` moved to
    ``rendercv.schema.models.cv.social_network``.

This script makes the minimum set of edits needed for ``manage.py`` to
import without ``ImportError`` so ``makemigrations`` can run. It does
**not** try to get rendering working — that's Phase 3's job, where we'll
rewrite the rendercv integration against the 2.x public API properly.

Files touched
-------------
* ``apps/cv/models.py``
    - Replaces ``from rendercv.data import read_a_yaml_file`` with a
      local pyyaml-backed helper.
    - Updates the ``available_social_networks`` import path.
    - Rewrites every call site: ``read_a_yaml_file(x)`` → ``_read_yaml_file(x)``.

* ``apps/cv/views.py``
    - Deletes the two module-level rendercv imports
      (``from rendercv import data`` / ``from rendercv.renderer import renderer``).
    - Injects a Phase-1 stopgap: ``data`` and ``renderer`` become proxy
      objects that import lazily, and if the 2.x import path doesn't
      match, raise ``NotImplementedError`` pointing at Phase 3. The module
      itself imports cleanly so Django's URL resolver is happy.

Idempotent. Safe to re-run. Preserves existing line endings (CRLF on
Windows checkouts, LF on unix).

Usage from the repo root::

    uv run python scripts/fix_rendercv_imports.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# models.py patches
# ---------------------------------------------------------------------------
MODELS_TARGET = Path("apps/cv/models.py")

MODELS_OLD_IMPORT_1 = "from rendercv.data import read_a_yaml_file"
MODELS_OLD_IMPORT_2 = "from rendercv.data.models.curriculum_vitae import available_social_networks"
MODELS_NEW_IMPORT_2 = "from rendercv.schema.models.cv.social_network import available_social_networks"

MODELS_HELPER = '''
import yaml as _yaml


def _read_yaml_file(path):
    """Drop-in replacement for rendercv 1.x's read_a_yaml_file."""
    with open(path, encoding="utf-8") as _f:
        return _yaml.safe_load(_f)
'''

# ---------------------------------------------------------------------------
# views.py patches
# ---------------------------------------------------------------------------
VIEWS_TARGET = Path("apps/cv/views.py")

VIEWS_OLD_IMPORT_DATA = "from rendercv import data"
VIEWS_OLD_IMPORT_RENDERER = "from rendercv.renderer import renderer"

# Sentinel pair used to detect and replace the block on a re-run. Kept as
# bare strings so the outer VIEWS_STOPGAP can be a plain (non-f) string.
VIEWS_STOPGAP_MARKER = "# --- rendercv 2.x stopgap (Phase 1, see scripts/fix_rendercv_imports.py) ---"
VIEWS_STOPGAP_END_MARKER = "# --- end rendercv 2.x stopgap ---"

# The shim is appended at EOF rather than spliced into the import block:
# Python resolves ``data`` and ``renderer`` inside view methods at call time,
# not at module-parse time, so binding them at the bottom of the module is
# sufficient and sidesteps any entanglement with multi-line bracketed imports.
VIEWS_STOPGAP = VIEWS_STOPGAP_MARKER + """
# rendercv 2.x removed the ``data`` module and reorganized ``renderer``.
# The views in this file were written against the 1.x private-ish API and
# will be rewritten in Phase 3 when PDF rendering is wired up for real.
# Until then, keep the module importable so makemigrations / reverse() work,
# and fail loudly if anyone actually tries to render a CV.
class _RendercvUnavailable:
    def __init__(self, what):
        self._what = what

    def _boom(self):
        raise NotImplementedError(
            "rendercv." + self._what + " is not wired up yet. "
            "PDF rendering is deferred to Phase 3 -- see ROADMAP.md."
        )

    def __getattr__(self, name):
        self._boom()

    def __call__(self, *args, **kwargs):
        self._boom()


data = _RendercvUnavailable("data")
renderer = _RendercvUnavailable("renderer")
""" + VIEWS_STOPGAP_END_MARKER


def _patch_models(src: str) -> tuple[str, list[str]]:
    """Return (new_src, messages)."""
    msgs: list[str] = []

    # 1. Replace read_a_yaml_file import with local helper.
    if MODELS_OLD_IMPORT_1 in src:
        src = src.replace(MODELS_OLD_IMPORT_1, MODELS_HELPER.strip())
        msgs.append("  patched: import of read_a_yaml_file replaced with local helper")
    elif "_read_yaml_file" in src:
        msgs.append("  skip:    local helper already present")
    else:
        msgs.append("  note:    neither old import nor helper found -- review manually")

    # 2. Swap social_networks import path.
    if MODELS_OLD_IMPORT_2 in src:
        src = src.replace(MODELS_OLD_IMPORT_2, MODELS_NEW_IMPORT_2)
        msgs.append("  patched: available_social_networks import path updated for rendercv 2.x")
    elif MODELS_NEW_IMPORT_2 in src:
        msgs.append("  skip:    social_networks import already on rendercv 2.x path")
    else:
        msgs.append("  note:    social_networks import not found -- review manually")

    # 3. Swap every call site.
    call_count = len(re.findall(r"\bread_a_yaml_file\(", src))
    if call_count:
        src = re.sub(r"\bread_a_yaml_file\(", "_read_yaml_file(", src)
        msgs.append(f"  patched: {call_count} call(s) to read_a_yaml_file -> _read_yaml_file")
    else:
        msgs.append("  skip:    no read_a_yaml_file call sites found")

    return src, msgs


def _patch_views(src: str) -> tuple[str, list[str]]:
    """Return (new_src, messages).

    Strategy:
      1. Remove any previously-injected stopgap block (marker-delimited) along
         with adjacent blank lines. This cleanly recovers from the earlier
         version of this script, which spliced the block into the import
         section and could land mid-way through a multi-line bracketed import.
      2. Strip the two module-level rendercv 1.x imports if still present.
      3. Append a fresh copy of the stopgap at EOF.

    Appending at EOF is safe because Python resolves ``data`` / ``renderer``
    references in view methods at call time, not parse time.
    """
    msgs: list[str] = []
    eol = "\r\n" if "\r\n" in src else "\n"

    # 1. Strip any prior shim block, plus surrounding blank lines, cleanly.
    lines = src.split(eol)
    start_idx = end_idx = None
    for i, line in enumerate(lines):
        if start_idx is None and VIEWS_STOPGAP_MARKER in line:
            start_idx = i
        elif start_idx is not None and VIEWS_STOPGAP_END_MARKER in line:
            end_idx = i
            break
    if start_idx is not None and end_idx is not None:
        # Expand the range to consume adjacent blank lines on both sides so we
        # don't leave double-blank gaps behind.
        while start_idx > 0 and lines[start_idx - 1].strip() == "":
            start_idx -= 1
        while end_idx < len(lines) - 1 and lines[end_idx + 1].strip() == "":
            end_idx += 1
        del lines[start_idx:end_idx + 1]
        src = eol.join(lines)
        msgs.append("  info:    removed existing stopgap shim")

    # 2. Strip module-level rendercv imports (whole line, including trailing newline).
    removed = 0
    for old in (VIEWS_OLD_IMPORT_DATA, VIEWS_OLD_IMPORT_RENDERER):
        pattern = re.compile(r"^" + re.escape(old) + r"\s*\r?\n", re.MULTILINE)
        new_src, n = pattern.subn("", src, count=1)
        if n:
            src = new_src
            removed += 1
    if removed:
        msgs.append(f"  patched: removed {removed} module-level rendercv import line(s)")
    else:
        msgs.append("  skip:    no module-level rendercv imports left to strip")

    # 3. Append the stopgap at EOF with exactly one blank line of separation.
    src = src.rstrip() + eol + eol + VIEWS_STOPGAP.strip() + eol
    msgs.append("  patched: appended rendercv 2.x stopgap shim at EOF")

    return src, msgs


def _apply(target: Path, patcher) -> bool:
    """Read, patch, and write back a single file. Returns True if changed."""
    if not target.exists():
        print(f"[{target}]")
        print(f"  ERROR: {target} not found. Run from the repo root.", file=sys.stderr)
        return False

    print(f"[{target}]")
    original = target.read_text(encoding="utf-8")
    src, msgs = patcher(original)
    for m in msgs:
        print(m)

    if src == original:
        print("  no changes.")
        return False

    # Preserve existing line endings.
    eol = "\r\n" if original.count("\r\n") > original.count("\n") // 2 else "\n"
    if eol == "\r\n":
        src = src.replace("\r\n", "\n").replace("\n", "\r\n")

    target.write_text(src, encoding="utf-8", newline="")
    print(f"  wrote {len(src)} chars.")
    return True


def main() -> int:
    any_missing = False
    for t in (MODELS_TARGET, VIEWS_TARGET):
        if not t.exists():
            any_missing = True
    if any_missing:
        print(
            "ERROR: expected to be run from the repo root where apps/cv/ exists. "
            "Did the Phase 1 migration finish?",
            file=sys.stderr,
        )
        return 1

    _apply(MODELS_TARGET, _patch_models)
    _apply(VIEWS_TARGET, _patch_views)
    return 0


if __name__ == "__main__":
    sys.exit(main())
