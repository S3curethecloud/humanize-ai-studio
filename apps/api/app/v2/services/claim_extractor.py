from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.v2.domain.claim_lock import (
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedClaim,
)

_EXTRACTOR_VERSION: Literal["claim-extractor-v1"] = "claim-extractor-v1"

_WORD_PATTERN = re.compile(
    r"\b[\w'-]+\b",
    re.UNICODE,
)

_NONTERMINAL_ABBREVIATIONS = frozenset(
    {
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "prof.",
        "sr.",
        "jr.",
        "vs.",
        "etc.",
        "e.g.",
        "i.e.",
    }
)

_DOTTED_INITIALISM_PATTERN = re.compile(r"(?:[A-Za-z]\.){2,}$")


class ClaimExtractionDecision(StrEnum):
    SELECTED = "selected"
    SKIPPED = "skipped"


class ClaimExtractionReason(StrEnum):
    SELECTED = "selected"
    BELOW_MINIMUM_WORDS = "below_minimum_words"
    QUESTION_EXCLUDED = "question_excluded"


class ClaimSelectionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    minimum_word_count: int = Field(
        default=3,
        ge=1,
        le=100,
    )
    include_questions: bool = False


class ClaimExtractionSegmentEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: int = Field(
        ge=0,
    )
    end: int = Field(
        ge=1,
    )
    matched_text: str = Field(
        min_length=1,
    )
    word_count: int = Field(
        ge=0,
    )
    decision: ClaimExtractionDecision
    reason: ClaimExtractionReason
    claim_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    @model_validator(mode="after")
    def require_coherent_decision_evidence(
        self,
    ) -> ClaimExtractionSegmentEvidence:
        if self.end <= self.start:
            raise ValueError("claim extraction segment end must be greater than start")

        if self.decision is ClaimExtractionDecision.SELECTED:
            if self.reason is not ClaimExtractionReason.SELECTED:
                raise ValueError("selected claim segment must use selected reason")

            if self.claim_id is None:
                raise ValueError("selected claim segment requires claim_id")

        else:
            if self.reason is ClaimExtractionReason.SELECTED:
                raise ValueError("skipped claim segment requires skip reason")

            if self.claim_id is not None:
                raise ValueError("skipped claim segment must not contain claim_id")

        return self


class ClaimExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    extractor_version: Literal["claim-extractor-v1"] = _EXTRACTOR_VERSION

    policy: ClaimSelectionPolicy
    claims: tuple[
        ProtectedClaim,
        ...,
    ] = ()
    segments: tuple[
        ClaimExtractionSegmentEvidence,
        ...,
    ] = ()

    @property
    def selected_count(
        self,
    ) -> int:
        return sum(
            segment.decision is ClaimExtractionDecision.SELECTED for segment in self.segments
        )

    @property
    def skipped_count(
        self,
    ) -> int:
        return sum(segment.decision is ClaimExtractionDecision.SKIPPED for segment in self.segments)


class ClaimExtractor:
    def extract(
        self,
        *,
        text: str,
        policy: ClaimSelectionPolicy | None = None,
        origin: ClaimLockOrigin = (ClaimLockOrigin.REQUEST),
        source_reference: str | None = ("rewrite-request"),
    ) -> ClaimExtractionResult:
        resolved_policy = policy or ClaimSelectionPolicy()

        provenance = ClaimLockProvenance(
            origin=origin,
            source_reference=source_reference,
        )

        claims_by_key: dict[
            str,
            ProtectedClaim,
        ] = {}

        segments: list[ClaimExtractionSegmentEvidence] = []

        for start, end in _statement_spans(text):
            matched_text = text[start:end]

            normalized_text = " ".join(matched_text.split())

            if not normalized_text:
                continue

            word_count = len(_WORD_PATTERN.findall(normalized_text))

            reason = _selection_reason(
                normalized_text=normalized_text,
                word_count=word_count,
                policy=resolved_policy,
            )

            if reason is not ClaimExtractionReason.SELECTED:
                segments.append(
                    ClaimExtractionSegmentEvidence(
                        start=start,
                        end=end,
                        matched_text=matched_text,
                        word_count=word_count,
                        decision=(ClaimExtractionDecision.SKIPPED),
                        reason=reason,
                    )
                )
                continue

            semantic_key = normalized_text.casefold()

            claim = claims_by_key.get(semantic_key)

            if claim is None:
                claim = ProtectedClaim(
                    claim_id=_stable_claim_id(semantic_key),
                    text=normalized_text,
                    provenance=provenance,
                )

                claims_by_key[semantic_key] = claim

            segments.append(
                ClaimExtractionSegmentEvidence(
                    start=start,
                    end=end,
                    matched_text=matched_text,
                    word_count=word_count,
                    decision=(ClaimExtractionDecision.SELECTED),
                    reason=(ClaimExtractionReason.SELECTED),
                    claim_id=claim.claim_id,
                )
            )

        return ClaimExtractionResult(
            policy=resolved_policy,
            claims=tuple(claims_by_key.values()),
            segments=tuple(segments),
        )


def _selection_reason(
    *,
    normalized_text: str,
    word_count: int,
    policy: ClaimSelectionPolicy,
) -> ClaimExtractionReason:
    if normalized_text.endswith("?") and not policy.include_questions:
        return ClaimExtractionReason.QUESTION_EXCLUDED

    if word_count < policy.minimum_word_count:
        return ClaimExtractionReason.BELOW_MINIMUM_WORDS

    return ClaimExtractionReason.SELECTED


def _statement_spans(
    text: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    spans: list[tuple[int, int]] = []

    segment_start = 0
    index = 0
    text_length = len(text)

    while index < text_length:
        character = text[index]

        if character == "\n":
            start, end = _trim_span(
                text,
                segment_start,
                index,
            )

            if start < end:
                spans.append((start, end))

            index += 1

            while index < text_length and text[index] == "\n":
                index += 1

            segment_start = index
            continue

        if character in "!?":
            next_index = index + 1

            if next_index == text_length or text[next_index].isspace():
                start, end = _trim_span(
                    text,
                    segment_start,
                    next_index,
                )

                if start < end:
                    spans.append((start, end))

                segment_start = next_index

        elif character == ".":
            next_index = index + 1

            if (
                (next_index == text_length) or text[next_index].isspace()
            ) and not _is_nonterminal_period(
                text=text,
                period_index=index,
                segment_start=segment_start,
            ):
                start, end = _trim_span(
                    text,
                    segment_start,
                    next_index,
                )

                if start < end:
                    spans.append((start, end))

                segment_start = next_index

        index += 1

    start, end = _trim_span(
        text,
        segment_start,
        text_length,
    )

    if start < end:
        spans.append((start, end))

    return tuple(spans)


def _is_nonterminal_period(
    *,
    text: str,
    period_index: int,
    segment_start: int,
) -> bool:
    token_start = period_index

    while token_start > segment_start and not text[token_start - 1].isspace():
        token_start -= 1

    token = text[token_start : period_index + 1]

    normalized = token.casefold()

    if normalized in _NONTERMINAL_ABBREVIATIONS:
        return True

    if len(token) == 2 and token[0].isalpha():
        return True

    return bool(_DOTTED_INITIALISM_PATTERN.fullmatch(token))


def _trim_span(
    text: str,
    start: int,
    end: int,
) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return (
        start,
        end,
    )


def _stable_claim_id(
    semantic_key: str,
) -> str:
    digest = hashlib.sha256(semantic_key.encode("utf-8")).hexdigest()[:20]

    return f"claim_{digest}"
