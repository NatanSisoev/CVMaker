"""Job-description tailoring: which of a CV's entries match a pasted posting?

Pure keyword overlap (no AI): tokenise the posting, drop stop words, and score
each entry by how many distinct posting keywords its text contains. The result
tells you what to emphasise or cut; it never edits anything.
"""

from __future__ import annotations

import re
from collections import Counter

from entries.models import BaseEntry

from .models import CV

_WORD = re.compile(r"[a-z][a-z0-9+#.\-]{1,}", re.IGNORECASE)
_STOP = frozenset(
    [
        "a",
        "about",
        "above",
        "after",
        "all",
        "also",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "more",
        "most",
        "must",
        "no",
        "not",
        "of",
        "on",
        "one",
        "or",
        "our",
        "out",
        "over",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "under",
        "up",
        "use",
        "used",
        "using",
        "via",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "will",
        "with",
        "within",
        "would",
        "you",
        "your",
        "experience",
        "work",
        "working",
        "team",
        "teams",
        "role",
        "years",
        "year",
        "ability",
        "strong",
        "skills",
        "including",
        "etc",
        "new",
    ]
)
MAX_TEXT = 20_000


def keywords(text: str, limit: int = 40) -> list[str]:
    """Most frequent non-stop-word terms of ``text`` (lowercased, trailing dots trimmed)."""
    counts = Counter(
        w.lower().rstrip(".-")
        for w in _WORD.findall(text[:MAX_TEXT])
        if w.lower() not in _STOP and len(w) > 2
    )
    return [word for word, _ in counts.most_common(limit)]


def _flatten(value) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, list | tuple):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def tailor_cv(cv: CV, posting: str) -> dict:
    """Rank the entries of ``cv`` against ``posting``."""
    words = keywords(posting)
    results = []
    for section in cv.sections.order_by("cvsection__order"):
        for link in section.section_entries.select_related("entry").order_by("order"):
            entry = BaseEntry.objects.select_subclasses().get(pk=link.entry_id)
            haystack = _flatten(entry.serialize()).lower()
            matched = [w for w in words if re.search(rf"(?<![a-z0-9]){re.escape(w)}", haystack)]
            results.append(
                {
                    "section": section.title,
                    "alias": entry.alias,
                    "matched": matched,
                    "score": len(matched),
                }
            )
    results.sort(key=lambda r: -r["score"])
    covered = {w for r in results for w in r["matched"]}
    return {
        "keywords": words,
        "ranked": results,
        "missing": [w for w in words if w not in covered],
    }
