from __future__ import annotations

import re
import unicodedata

_SPACE_PATTERN = re.compile(r"\s+")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s%$.\-]", re.UNICODE)


def normalize_evaluation_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)

    normalized = (
        normalized.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .casefold()
    )

    normalized = _PUNCTUATION_PATTERN.sub(" ", normalized)
    normalized = _SPACE_PATTERN.sub(" ", normalized)

    return normalized.strip().rstrip(".")
