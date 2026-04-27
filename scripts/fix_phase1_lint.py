"""
One-shot Phase 1 polish: fix the handful of lint issues in the code we
wrote this phase (not the legacy apps -- those get scoped out in
pyproject.toml's per-file-ignores). Idempotent. Preserves CRLF.

Files touched
-------------
* ``apps/accounts/models.py``
    - Drop the quoted ``-> "User"`` METHOD annotations (3 sites). With
      ``from __future__ import annotations`` at the top, method-return
      annotations are lazy strings; re-quoting them trips ruff UP037.
    - NOTE: ``BaseUserManager["User"]`` in the *class-base* position is
      NOT an annotation -- it's evaluated at class-creation time, before
      ``User`` is defined later in the file. Keep the quotes there and
      silence UP037 with an inline ``# noqa``.
    - Annotate ``REQUIRED_FIELDS`` as ``ClassVar[list[str]]`` so ruff's
      RUF012 (mutable class attribute) is satisfied without giving up the
      obvious list literal.

* ``apps/accounts/tests.py``
    - Drop the default ``from django.test import TestCase`` scaffold import
      (F401 -- it's just Django's ``startapp`` boilerplate).

Run from the repo root::

    uv run python scripts/fix_phase1_lint.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ACCOUNTS_MODELS = Path("apps/accounts/models.py")
ACCOUNTS_TESTS = Path("apps/accounts/tests.py")


def _write(path: Path, new: str, original: str) -> bool:
    if new == original:
        return False
    eol = "\r\n" if original.count("\r\n") > original.count("\n") // 2 else "\n"
    if eol == "\r\n":
        new = new.replace("\r\n", "\n").replace("\n", "\r\n")
    path.write_text(new, encoding="utf-8", newline="")
    return True


def _patch_accounts_models(src: str) -> str:
    # UP037 on method returns: with ``from __future__ import annotations``,
    # ``-> "User"`` is a redundantly-quoted lazy annotation. Drop the quotes.
    src = re.sub(r'->\s*"User"', "-> User", src)

    # ``BaseUserManager["User"]`` in the *class-base* position is NOT an
    # annotation -- a class base is evaluated at class-creation time, so we
    # can't drop the quotes (User isn't defined yet). Ruff used to flag this
    # as UP037 but turns out RUF100 then also reports a no-op noqa, so just
    # keep the quotes and let ruff stay quiet on its own.
    #
    # If a previous run dropped the quotes (older buggy revision of this
    # script), put them back -- otherwise Python raises NameError at import.
    src = src.replace(
        "class UserManager(BaseUserManager[User]):",
        'class UserManager(BaseUserManager["User"]):',
    )

    # RUF012: REQUIRED_FIELDS is a mutable class attribute on ``User``.
    # Annotate with ClassVar so ruff is happy; pyright/mypy then see it as a
    # read-only class-level declaration, which matches Django's semantics.
    if "from typing import ClassVar" not in src:
        src = src.replace(
            "from django.contrib.auth.models import AbstractUser, BaseUserManager",
            "from typing import ClassVar\n\n"
            "from django.contrib.auth.models import AbstractUser, BaseUserManager",
            1,
        )
    src = src.replace(
        'REQUIRED_FIELDS = ["username"]',
        'REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]',
    )
    return src


def _patch_accounts_tests(src: str) -> str:
    # Strip Django's stock ``from django.test import TestCase`` + the matching
    # "Create your tests here." stub. If the user later adds real tests, they
    # re-import explicitly.
    lines = src.splitlines(keepends=False)
    new = []
    for line in lines:
        if line.strip() == "from django.test import TestCase":
            continue
        new.append(line)
    return "\n".join(new) + ("\n" if src.endswith(("\n", "\r\n")) else "")


def _apply(path: Path, patcher) -> None:
    if not path.exists():
        print(f"[{path}]\n  ERROR: not found.", file=sys.stderr)
        return
    original = path.read_text(encoding="utf-8")
    new = patcher(original)
    changed = _write(path, new, original)
    print(f"[{path}] {'wrote' if changed else 'no changes'}")


def main() -> int:
    _apply(ACCOUNTS_MODELS, _patch_accounts_models)
    _apply(ACCOUNTS_TESTS, _patch_accounts_tests)
    return 0


if __name__ == "__main__":
    sys.exit(main())
