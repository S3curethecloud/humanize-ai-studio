from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.domain.models import RewriteIntensity

_TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b")
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]+")
_MINIMUM_POSITION_SHIFT = 0.20
_MINIMUM_DEEP_MOVED_TOKENS = 3


@dataclass(frozen=True)
class RewriteDistanceResult:
    acceptable: bool
    similarity_ratio: float
    changed_token_count: int
    moved_token_count: int
    source_sentence_count: int
    rewritten_sentence_count: int
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
    moved_token_count = _moved_token_count(
        source_text,
        rewritten_text,
    )
    source_sentence_count = _sentence_count(source_text)
    rewritten_sentence_count = _sentence_count(rewritten_text)

    def build_result(
        *,
        acceptable: bool,
        reason: str,
    ) -> RewriteDistanceResult:
        return RewriteDistanceResult(
            acceptable=acceptable,
            similarity_ratio=similarity_ratio,
            changed_token_count=changed_token_count,
            moved_token_count=moved_token_count,
            source_sentence_count=source_sentence_count,
            rewritten_sentence_count=rewritten_sentence_count,
            reason=reason,
        )

    if normalized_source == normalized_rewrite:
        return build_result(
            acceptable=False,
            reason="The rewrite is textually identical to the source.",
        )

    if intensity == RewriteIntensity.LIGHT_EDIT:
        return build_result(
            acceptable=True,
            reason="The light edit produced a textual change.",
        )

    if changed_token_count < 1:
        return build_result(
            acceptable=False,
            reason=(
                "The rewrite did not make a meaningful lexical change for the requested intensity."
            ),
        )

    if intensity == RewriteIntensity.DEEP_RECONSTRUCTION:
        sentence_structure_changed = source_sentence_count != rewritten_sentence_count
        information_order_changed = moved_token_count >= _MINIMUM_DEEP_MOVED_TOKENS

        if not (sentence_structure_changed or information_order_changed):
            return build_result(
                acceptable=False,
                reason=(
                    "The deep reconstruction changed wording "
                    "without materially changing sentence "
                    "structure or information order."
                ),
            )

    return build_result(
        acceptable=True,
        reason=(
            "The rewrite satisfied the lexical and structural "
            "distance contract for the requested intensity."
        ),
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

    for (
        tag,
        source_start,
        source_end,
        rewrite_start,
        rewrite_end,
    ) in matcher.get_opcodes():
        if tag == "equal":
            continue

        changed += max(
            source_end - source_start,
            rewrite_end - rewrite_start,
        )

    return changed


def _moved_token_count(
    source_text: str,
    rewritten_text: str,
) -> int:
    source_tokens = _tokens(source_text)
    rewrite_tokens = _tokens(rewritten_text)

    if len(source_tokens) < 2 or len(rewrite_tokens) < 2:
        return 0

    source_counts = Counter(source_tokens)
    rewrite_counts = Counter(rewrite_tokens)

    source_positions = {
        token: index
        for index, token in enumerate(source_tokens)
        if source_counts[token] == 1 and rewrite_counts[token] == 1
    }
    rewrite_positions = {
        token: index
        for index, token in enumerate(rewrite_tokens)
        if source_counts[token] == 1 and rewrite_counts[token] == 1
    }

    source_denominator = max(len(source_tokens) - 1, 1)
    rewrite_denominator = max(len(rewrite_tokens) - 1, 1)

    moved = 0

    for token, source_index in source_positions.items():
        rewrite_index = rewrite_positions.get(token)

        if rewrite_index is None:
            continue

        source_position = source_index / source_denominator
        rewrite_position = rewrite_index / rewrite_denominator

        if abs(source_position - rewrite_position) >= _MINIMUM_POSITION_SHIFT:
            moved += 1

    return moved


def _sentence_count(value: str) -> int:
    segments = [segment for segment in _SENTENCE_BOUNDARY_PATTERN.split(value) if segment.strip()]

    return max(len(segments), 1)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN_PATTERN.findall(value))


def follows_deep_repair_blueprint(
    *,
    source_text: str,
    rewritten_text: str,
) -> bool:
    source_sentences = _sentences(source_text)

    if len(source_sentences) < 2:
        return (
            _sentence_count(rewritten_text) >= 2
            and _moved_token_count(
                source_text,
                rewritten_text,
            )
            >= _MINIMUM_DEEP_MOVED_TOKENS
        )

    first_source_tokens = set(_tokens(source_sentences[0]))
    final_source_tokens = set(_tokens(source_sentences[-1]))

    final_distinctive_tokens = final_source_tokens - first_source_tokens

    if not final_distinctive_tokens:
        return False

    rewritten_tokens = _tokens(rewritten_text)

    if not rewritten_tokens:
        return False

    opening_length = max(
        5,
        round(len(rewritten_tokens) * 0.35),
    )
    opening_tokens = set(rewritten_tokens[:opening_length])

    return bool(opening_tokens & final_distinctive_tokens)


def _sentences(value: str) -> tuple[str, ...]:
    return tuple(
        segment.strip() for segment in _SENTENCE_BOUNDARY_PATTERN.split(value) if segment.strip()
    )
