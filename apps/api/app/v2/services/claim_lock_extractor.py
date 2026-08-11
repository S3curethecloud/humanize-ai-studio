from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.v2.domain.claim_lock import (
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
    ProtectedValue,
    ProtectedValueKind,
)

_EXTRACTOR_VERSION: Literal["claim-lock-extractor-v1"] = "claim-lock-extractor-v1"

_MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

_URL_PATTERN = re.compile(
    r"""https?://[^\s<>"']+""",
    re.IGNORECASE,
)

_PERCENTAGE_PATTERN = re.compile(
    r"""(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s?%(?!\w)"""
)

_ISO_DATE_PATTERN = re.compile(r"""\b\d{4}-\d{2}-\d{2}\b""")

_SLASH_DATE_PATTERN = re.compile(r"""\b\d{1,2}/\d{1,2}/\d{2,4}\b""")

_MONTH_DATE_PATTERN = re.compile(
    rf"""\b(?:{_MONTHS})\s+\d{{1,2}}(?:,\s*\d{{4}})?\b""",
    re.IGNORECASE,
)

_CODE_PATTERN = re.compile(
    r"""
    \b
    (?=[A-Za-z0-9_-]*[A-Za-z])
    (?=[A-Za-z0-9_-]*\d)
    [A-Za-z0-9]+
    (?:[-_][A-Za-z0-9]+)+
    \b
    """,
    re.VERBOSE,
)

_IDENTIFIER_PATTERN = re.compile(
    r"""
    \b
    (?=[A-Za-z0-9]*[A-Za-z])
    (?=[A-Za-z0-9]*\d)
    [A-Za-z0-9]{6,}
    \b
    """,
    re.VERBOSE,
)

_NUMBER_PATTERN = re.compile(
    r"""
    (?<![\w.-])
    [$€£]?
    (?:\d{1,3}(?:,\d{3})+|\d+)
    (?:\.\d+)?
    (?![\w%]|\.\d)
    """,
    re.VERBOSE,
)

_TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


class ClaimLockExtractionDetector(StrEnum):
    EXPLICIT_TERM = "explicit_term"
    URL = "url"
    PERCENTAGE = "percentage"
    DATE = "date"
    CODE = "code"
    IDENTIFIER = "identifier"
    NUMBER = "number"


class ExplicitProtectedTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(
        min_length=1,
        max_length=1000,
    )
    case_sensitive: bool = True

    @field_validator(
        "text",
        mode="before",
    )
    @classmethod
    def normalize_text(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError("text must be non-empty")

        return normalized


class ClaimLockExtractionOccurrence(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str = Field(
        min_length=1,
        max_length=200,
    )
    item_type: Literal[
        "term",
        "value",
    ]
    detector: ClaimLockExtractionDetector
    start: int = Field(
        ge=0,
    )
    end: int = Field(
        ge=1,
    )
    matched_text: str = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_valid_span(
        self,
    ) -> ClaimLockExtractionOccurrence:
        if self.end <= self.start:
            raise ValueError("extraction occurrence end must be greater than start")

        return self


class ClaimLockExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    extractor_version: Literal["claim-lock-extractor-v1"] = _EXTRACTOR_VERSION

    terms: tuple[
        ProtectedTerm,
        ...,
    ] = ()
    values: tuple[
        ProtectedValue,
        ...,
    ] = ()
    occurrences: tuple[
        ClaimLockExtractionOccurrence,
        ...,
    ] = ()


class _ValueCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: int
    end: int
    matched_text: str
    kind: ProtectedValueKind
    detector: ClaimLockExtractionDetector
    priority: int


class ClaimLockExtractor:
    def extract(
        self,
        *,
        text: str,
        explicit_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        origin: ClaimLockOrigin = (ClaimLockOrigin.REQUEST),
        source_reference: str | None = ("rewrite-request"),
    ) -> ClaimLockExtractionResult:
        provenance = ClaimLockProvenance(
            origin=origin,
            source_reference=source_reference,
        )

        terms, term_occurrences = self._extract_explicit_terms(
            text=text,
            explicit_terms=explicit_terms,
            provenance=provenance,
        )

        values, value_occurrences = self._extract_values(
            text=text,
            provenance=provenance,
        )

        occurrences = tuple(
            sorted(
                (
                    *term_occurrences,
                    *value_occurrences,
                ),
                key=lambda occurrence: (
                    occurrence.start,
                    occurrence.end,
                    occurrence.item_type,
                    occurrence.item_id,
                ),
            )
        )

        return ClaimLockExtractionResult(
            terms=terms,
            values=values,
            occurrences=occurrences,
        )

    def _extract_explicit_terms(
        self,
        *,
        text: str,
        explicit_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ],
        provenance: ClaimLockProvenance,
    ) -> tuple[
        tuple[ProtectedTerm, ...],
        tuple[
            ClaimLockExtractionOccurrence,
            ...,
        ],
    ]:
        terms_by_key: dict[
            str,
            ProtectedTerm,
        ] = {}

        occurrences: list[ClaimLockExtractionOccurrence] = []

        for seed in explicit_terms:
            semantic_key = seed.text.casefold()

            term = terms_by_key.get(semantic_key)

            if term is None:
                term_id = _stable_id(
                    prefix="term",
                    parts=(semantic_key,),
                )

                term = ProtectedTerm(
                    term_id=term_id,
                    text=seed.text,
                    case_sensitive=(seed.case_sensitive),
                    provenance=provenance,
                )

                terms_by_key[semantic_key] = term

            pattern = _explicit_term_pattern(seed.text)

            flags = 0 if seed.case_sensitive else re.IGNORECASE

            for match in re.finditer(
                pattern,
                text,
                flags=flags,
            ):
                occurrences.append(
                    ClaimLockExtractionOccurrence(
                        item_id=term.term_id,
                        item_type="term",
                        detector=(ClaimLockExtractionDetector.EXPLICIT_TERM),
                        start=match.start(),
                        end=match.end(),
                        matched_text=(match.group(0)),
                    )
                )

        matched_term_ids = {occurrence.item_id for occurrence in occurrences}

        matched_terms = tuple(
            term for term in terms_by_key.values() if term.term_id in matched_term_ids
        )

        return (
            matched_terms,
            tuple(occurrences),
        )

    def _extract_values(
        self,
        *,
        text: str,
        provenance: ClaimLockProvenance,
    ) -> tuple[
        tuple[ProtectedValue, ...],
        tuple[
            ClaimLockExtractionOccurrence,
            ...,
        ],
    ]:
        candidates: list[_ValueCandidate] = []

        candidates.extend(
            _regex_candidates(
                text=text,
                pattern=_URL_PATTERN,
                kind=ProtectedValueKind.URL,
                detector=(ClaimLockExtractionDetector.URL),
                priority=10,
                trim_url=True,
            )
        )

        candidates.extend(
            _regex_candidates(
                text=text,
                pattern=_PERCENTAGE_PATTERN,
                kind=(ProtectedValueKind.PERCENTAGE),
                detector=(ClaimLockExtractionDetector.PERCENTAGE),
                priority=20,
            )
        )

        for date_pattern in (
            _ISO_DATE_PATTERN,
            _SLASH_DATE_PATTERN,
            _MONTH_DATE_PATTERN,
        ):
            candidates.extend(
                _regex_candidates(
                    text=text,
                    pattern=date_pattern,
                    kind=ProtectedValueKind.DATE,
                    detector=(ClaimLockExtractionDetector.DATE),
                    priority=30,
                )
            )

        candidates.extend(
            _regex_candidates(
                text=text,
                pattern=_CODE_PATTERN,
                kind=ProtectedValueKind.CODE,
                detector=(ClaimLockExtractionDetector.CODE),
                priority=40,
            )
        )

        candidates.extend(
            _regex_candidates(
                text=text,
                pattern=(_IDENTIFIER_PATTERN),
                kind=(ProtectedValueKind.IDENTIFIER),
                detector=(ClaimLockExtractionDetector.IDENTIFIER),
                priority=50,
            )
        )

        candidates.extend(
            _regex_candidates(
                text=text,
                pattern=_NUMBER_PATTERN,
                kind=ProtectedValueKind.NUMBER,
                detector=(ClaimLockExtractionDetector.NUMBER),
                priority=60,
            )
        )

        accepted = _resolve_value_overlaps(candidates)

        values_by_key: dict[
            tuple[
                ProtectedValueKind,
                str,
            ],
            ProtectedValue,
        ] = {}

        occurrences: list[ClaimLockExtractionOccurrence] = []

        for candidate in accepted:
            semantic_key = (
                candidate.kind,
                candidate.matched_text.casefold(),
            )

            value = values_by_key.get(semantic_key)

            if value is None:
                value_id = _stable_id(
                    prefix="value",
                    parts=(
                        candidate.kind.value,
                        candidate.matched_text.casefold(),
                    ),
                )

                value = ProtectedValue(
                    value_id=value_id,
                    value=(candidate.matched_text),
                    kind=candidate.kind,
                    provenance=provenance,
                )

                values_by_key[semantic_key] = value

            occurrences.append(
                ClaimLockExtractionOccurrence(
                    item_id=value.value_id,
                    item_type="value",
                    detector=(candidate.detector),
                    start=candidate.start,
                    end=candidate.end,
                    matched_text=(candidate.matched_text),
                )
            )

        values = tuple(
            sorted(
                values_by_key.values(),
                key=lambda value: (
                    _first_occurrence_start(
                        value.value_id,
                        occurrences,
                    ),
                    value.kind.value,
                    value.value_id,
                ),
            )
        )

        return (
            values,
            tuple(occurrences),
        )


def _explicit_term_pattern(
    text: str,
) -> str:
    parts = text.split()

    return r"\s+".join(re.escape(part) for part in parts)


def _stable_id(
    *,
    prefix: str,
    parts: tuple[str, ...],
) -> str:
    canonical = "\x1f".join(parts).encode("utf-8")

    digest = hashlib.sha256(canonical).hexdigest()[:20]

    return f"{prefix}_{digest}"


def _regex_candidates(
    *,
    text: str,
    pattern: re.Pattern[str],
    kind: ProtectedValueKind,
    detector: ClaimLockExtractionDetector,
    priority: int,
    trim_url: bool = False,
) -> tuple[_ValueCandidate, ...]:
    candidates: list[_ValueCandidate] = []

    for match in pattern.finditer(text):
        start = match.start()
        end = match.end()
        matched_text = match.group(0)

        if trim_url:
            trimmed = matched_text.rstrip(_TRAILING_URL_PUNCTUATION)

            if not trimmed:
                continue

            end -= len(matched_text) - len(trimmed)
            matched_text = trimmed

        candidates.append(
            _ValueCandidate(
                start=start,
                end=end,
                matched_text=matched_text,
                kind=kind,
                detector=detector,
                priority=priority,
            )
        )

    return tuple(candidates)


def _resolve_value_overlaps(
    candidates: list[_ValueCandidate],
) -> tuple[_ValueCandidate, ...]:
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            candidate.priority,
            candidate.start,
            -(candidate.end - candidate.start),
            candidate.matched_text,
        ),
    )

    accepted: list[_ValueCandidate] = []

    for candidate in ordered:
        if any(
            _spans_overlap(
                candidate.start,
                candidate.end,
                existing.start,
                existing.end,
            )
            for existing in accepted
        ):
            continue

        accepted.append(candidate)

    return tuple(
        sorted(
            accepted,
            key=lambda candidate: (
                candidate.start,
                candidate.end,
                candidate.priority,
            ),
        )
    )


def _spans_overlap(
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> bool:
    return left_start < right_end and right_start < left_end


def _first_occurrence_start(
    item_id: str,
    occurrences: list[ClaimLockExtractionOccurrence],
) -> int:
    return min(occurrence.start for occurrence in occurrences if occurrence.item_id == item_id)
