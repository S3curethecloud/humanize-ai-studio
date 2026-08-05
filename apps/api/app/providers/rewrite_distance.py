from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.domain.models import RewriteIntensity

_TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b")


@dataclass(frozen=True)
class RewriteDistanceResult:
    acceptable: bool
    similarity_ratio: float
    changed_token_count: int
    reason: str


def evaluate_rewrite_distance(
    *,
    source_text: str,
    rewritten_text: str,
    intensity: RewriteIntensity,
) -> RewriteDistanceResult:
    normalized_source = _normalize_text(source_text)
    normalized_rewrite = _normalize_text(rewritten_text)

    similarity_ratio = SequenceMatcher(
        None,
        normalized_source,
        normalized_rewrite,
    ).ratio()

    changed_token_count = _changed_token_count(
        source_text,
        rewritten_text,
    )

    if normalized_source == normalized_rewrite:
        return RewriteDistanceResult(
            acceptable=False,
            similarity_ratio=similarity_ratio,
            changed_token_count=0,
            reason="The rewrite is textually identical to the source.",
        )

    if intensity == RewriteIntensity.LIGHT_EDIT:
        return RewriteDistanceResult(
            acceptable=True,
            similarity_ratio=similarity_ratio,
            changed_token_count=changed_token_count,
            reason="Light polish produced a textual change.",
        )

    minimum_changed_tokens = 1 if intensity == RewriteIntensity.NATURAL_REWRITE else 3

    if changed_token_count < minimum_changed_tokens:
        return RewriteDistanceResult(
            acceptable=False,
            similarity_ratio=similarity_ratio,
            changed_token_count=changed_token_count,
            reason=(
                "The rewrite did not make enough lexical or structural "
                "changes for the requested intensity."
            ),
        )

    return RewriteDistanceResult(
        acceptable=True,
        similarity_ratio=similarity_ratio,
        changed_token_count=changed_token_count,
        reason="The rewrite satisfied the minimum useful-distance contract.",
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _changed_token_count(
    source_text: str,
    rewritten_text: str,
) -> int:
    source_tokens = _tokens(source_text)
    rewrite_tokens = _tokens(rewritten_text)

    matcher = SequenceMatcher(
        None,
        source_tokens,
        rewrite_tokens,
    )

    changed = 0

    for tag, source_start, source_end, rewrite_start, rewrite_end in matcher.get_opcodes():
        if tag == "equal":
            continue

        changed += max(
            source_end - source_start,
            rewrite_end - rewrite_start,
        )

    return changed


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN_PATTERN.findall(value))
