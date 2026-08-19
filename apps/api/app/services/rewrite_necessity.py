from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field


class RewriteDecision(StrEnum):
    NO_CHANGE = "no_change"
    MINIMAL_EDIT = "minimal_edit"
    FULL_REWRITE = "full_rewrite"


class RewriteSignalType(StrEnum):
    FORMULAIC_LANGUAGE = "formulaic_language"
    REPETITION = "repetition"
    VERBOSITY = "verbosity"
    INTENSITY_REQUEST = "intensity_request"
    ALREADY_CLEAR = "already_clear"


class RewriteSignal(BaseModel):
    signal_type: RewriteSignalType
    description: str
    score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)


class RewriteNecessityRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    document_type: str | None = None
    audience: str | None = None
    tone: str | None = None
    intensity: str = "natural_rewrite"


class RewriteNecessityResult(BaseModel):
    decision: RewriteDecision
    score: int = Field(ge=0, le=100)
    original_text: str
    candidate_text: str | None
    provider_required: bool
    signals: list[RewriteSignal] = Field(default_factory=list)
    rationale: str


_FORMULAIC_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)(?<!\w)furthermore,\s*",
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(?<!\w)additionally,\s*",
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(?<!\w)moreover,\s*",
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(?<!\w)it is important to note that\s+",
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(?<!\w)it should be noted that\s+",
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(?<!\w)in conclusion,\s*",
        ),
        "",
    ),
)

_FORMULAIC_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bfurthermore\b"), "furthermore"),
    (re.compile(r"(?i)\badditionally\b"), "additionally"),
    (re.compile(r"(?i)\bmoreover\b"), "moreover"),
    (
        re.compile(r"(?i)\bit is important to note that\b"),
        "it is important to note that",
    ),
    (
        re.compile(r"(?i)\bit should be noted that\b"),
        "it should be noted that",
    ),
    (re.compile(r"(?i)\bin conclusion\b"), "in conclusion"),
)

_PROVIDER_REWRITE_INTENSITIES = {
    "natural_rewrite",
    "full_rewrite",
    "substantial_rewrite",
    "aggressive_rewrite",
    "deep_reconstruction",
}

_MINIMAL_EDIT_INTENSITIES = {
    "light_touch",
    "minimal_edit",
    "copy_edit",
    "light_edit",
}

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_WORD_PATTERN = re.compile(r"\b[\w'-]+\b")


class RewriteNecessityAnalyzer:
    def analyze(
        self,
        request: RewriteNecessityRequest,
    ) -> RewriteNecessityResult:
        text = request.text.strip()

        signals: list[RewriteSignal] = []

        formulaic_matches = self._find_formulaic_language(text)

        if formulaic_matches:
            signals.append(
                RewriteSignal(
                    signal_type=RewriteSignalType.FORMULAIC_LANGUAGE,
                    description=(
                        "Localized formulaic language can be removed "
                        "without reconstructing the document."
                    ),
                    score=min(30, 10 * len(formulaic_matches)),
                    evidence=formulaic_matches,
                )
            )

        repetition_evidence = self._find_repetition(text)

        if repetition_evidence:
            repetition_score = min(
                50,
                15 + (10 * len(repetition_evidence)),
            )
            signals.append(
                RewriteSignal(
                    signal_type=RewriteSignalType.REPETITION,
                    description=(
                        "Repeated sentence openings or repeated clauses reduce natural flow."
                    ),
                    score=repetition_score,
                    evidence=repetition_evidence,
                )
            )

        verbosity_evidence = self._find_verbosity(text)

        if verbosity_evidence:
            signals.append(
                RewriteSignal(
                    signal_type=RewriteSignalType.VERBOSITY,
                    description=(
                        "The text contains long or structurally dense "
                        "sentences that may benefit from reconstruction."
                    ),
                    score=min(
                        35,
                        10 + (5 * len(verbosity_evidence)),
                    ),
                    evidence=verbosity_evidence,
                )
            )

        normalized_intensity = request.intensity.strip().casefold()

        if normalized_intensity in _PROVIDER_REWRITE_INTENSITIES:
            signals.append(
                RewriteSignal(
                    signal_type=RewriteSignalType.INTENSITY_REQUEST,
                    description=(
                        "The requested intensity explicitly authorizes generative rewriting."
                    ),
                    score=60,
                    evidence=[request.intensity],
                )
            )

        decision = self._decide(
            signals=signals,
            intensity=normalized_intensity,
        )

        score = min(
            100,
            sum(signal.score for signal in signals),
        )

        if decision is RewriteDecision.NO_CHANGE:
            return RewriteNecessityResult(
                decision=decision,
                score=0,
                original_text=text,
                candidate_text=text,
                provider_required=False,
                signals=[
                    RewriteSignal(
                        signal_type=RewriteSignalType.ALREADY_CLEAR,
                        description=("No measurable rewrite need was detected."),
                        score=0,
                    )
                ],
                rationale=(
                    "The text is already clear enough to preserve exactly. "
                    "Provider execution is not justified."
                ),
            )

        if decision is RewriteDecision.MINIMAL_EDIT:
            candidate = self._apply_minimal_edits(text)

            return RewriteNecessityResult(
                decision=decision,
                score=score,
                original_text=text,
                candidate_text=candidate,
                provider_required=False,
                signals=signals,
                rationale=(
                    "The detected issues are localized and can be corrected "
                    "deterministically without broad sentence reconstruction."
                ),
            )

        return RewriteNecessityResult(
            decision=decision,
            score=score,
            original_text=text,
            candidate_text=None,
            provider_required=True,
            signals=signals,
            rationale=(
                "The text contains structural rewrite needs or the requested "
                "intensity explicitly requires governed generative rewriting."
            ),
        )

    def _decide(
        self,
        *,
        signals: list[RewriteSignal],
        intensity: str,
    ) -> RewriteDecision:
        if intensity in _PROVIDER_REWRITE_INTENSITIES:
            return RewriteDecision.FULL_REWRITE

        if not signals:
            return RewriteDecision.NO_CHANGE

        signal_types = {signal.signal_type for signal in signals}

        repetition_signal = next(
            (signal for signal in signals if signal.signal_type is RewriteSignalType.REPETITION),
            None,
        )

        if repetition_signal is not None and repetition_signal.score >= 35:
            return RewriteDecision.FULL_REWRITE

        if RewriteSignalType.VERBOSITY in signal_types:
            return RewriteDecision.FULL_REWRITE

        if intensity in _MINIMAL_EDIT_INTENSITIES:
            return RewriteDecision.MINIMAL_EDIT

        if signal_types == {RewriteSignalType.FORMULAIC_LANGUAGE}:
            return RewriteDecision.MINIMAL_EDIT

        return RewriteDecision.FULL_REWRITE

    def _find_formulaic_language(
        self,
        text: str,
    ) -> list[str]:
        evidence: list[str] = []

        for pattern, label in _FORMULAIC_LABELS:
            if pattern.search(text):
                evidence.append(label)

        return evidence

    def _find_repetition(
        self,
        text: str,
    ) -> list[str]:
        sentences = [
            sentence.strip() for sentence in _SENTENCE_SPLIT_PATTERN.split(text) if sentence.strip()
        ]

        openings: dict[str, int] = {}

        for sentence in sentences:
            words = _WORD_PATTERN.findall(sentence.casefold())

            if len(words) < 2:
                continue

            opening = " ".join(words[:2])
            openings[opening] = openings.get(opening, 0) + 1

        return [
            f'Repeated sentence opening: "{opening}" ({count} times)'
            for opening, count in sorted(openings.items())
            if count >= 3
        ]

    def _find_verbosity(
        self,
        text: str,
    ) -> list[str]:
        sentences = [
            sentence.strip() for sentence in _SENTENCE_SPLIT_PATTERN.split(text) if sentence.strip()
        ]

        evidence: list[str] = []

        for index, sentence in enumerate(sentences, start=1):
            word_count = len(_WORD_PATTERN.findall(sentence))

            if word_count >= 45:
                evidence.append(f"Sentence {index} contains {word_count} words.")

        return evidence

    def _apply_minimal_edits(
        self,
        text: str,
    ) -> str:
        candidate = text

        for pattern, replacement in _FORMULAIC_REPLACEMENTS:
            candidate = pattern.sub(replacement, candidate)

        candidate = re.sub(r"[ \t]{2,}", " ", candidate)
        candidate = re.sub(r"\s+([,.;:!?])", r"\1", candidate)
        candidate = candidate.strip()

        if candidate:
            candidate = candidate[0].upper() + candidate[1:]

        return candidate
