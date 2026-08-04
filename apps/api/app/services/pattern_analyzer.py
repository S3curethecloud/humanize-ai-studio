from __future__ import annotations

import re
from collections import Counter

from app.domain.models import AnalysisResult, FlaggedSegment, PatternScores, TextSpan

GENERIC_PHRASES = (
    "in today's rapidly evolving",
    "it is important to note",
    "in conclusion",
    "furthermore",
    "moreover",
    "delve into",
    "a testament to",
    "in the realm of",
)

TRANSITIONS = (
    "furthermore",
    "moreover",
    "additionally",
    "consequently",
    "therefore",
)


class PatternAnalyzer:
    def analyze(self, text: str) -> AnalysisResult:
        lowered = text.lower()
        flagged: list[FlaggedSegment] = []

        for phrase in GENERIC_PHRASES:
            for match in re.finditer(re.escape(phrase), lowered):
                flagged.append(
                    FlaggedSegment(
                        text=text[match.start() : match.end()],
                        reason="generic_or_formulaic_phrase",
                        source_span=TextSpan(start=match.start(), end=match.end()),
                    )
                )

        words = re.findall(r"\b[\w'-]+\b", lowered)
        word_counts = Counter(words)
        repeated_words = sum(
            count - 2 for word, count in word_counts.items() if count > 2 and len(word) > 4
        )
        repetition_score = min(repeated_words / max(len(words), 1), 1.0)

        sentences = [sentence.strip() for sentence in re.split(r"[.!?]+", text) if sentence.strip()]
        sentence_lengths = [len(sentence.split()) for sentence in sentences]

        if len(sentence_lengths) < 2:
            uniformity_score = 0.0
        else:
            average = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((length - average) ** 2 for length in sentence_lengths)
            variance /= len(sentence_lengths)
            uniformity_score = max(0.0, min(1.0, 1.0 - variance / max(average**2, 1.0)))

        transition_count = sum(lowered.count(transition) for transition in TRANSITIONS)
        transition_score = min(transition_count / max(len(sentences), 1), 1.0)

        generic_score = min(len(flagged) / max(len(sentences), 1), 1.0)

        return AnalysisResult(
            scores=PatternScores(
                generic_language=round(generic_score, 3),
                repetition=round(repetition_score, 3),
                sentence_uniformity=round(uniformity_score, 3),
                transition_overuse=round(transition_score, 3),
            ),
            flagged_segments=flagged,
        )
