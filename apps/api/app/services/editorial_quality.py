from __future__ import annotations

from app.domain.models import (
    AnalysisResult,
    EditorialQualityDecision,
    EditorialQualityResult,
)
from app.services.pattern_analyzer import PatternAnalyzer


class EditorialQualityEvaluator:
    def __init__(
        self,
        analyzer: PatternAnalyzer | None = None,
        *,
        minimum_naturalness_score: float = 0.75,
    ) -> None:
        if not 0.0 <= minimum_naturalness_score <= 1.0:
            raise ValueError("minimum_naturalness_score must be between 0.0 and 1.0.")

        self._analyzer = analyzer or PatternAnalyzer()
        self._minimum_naturalness_score = minimum_naturalness_score

    def evaluate(
        self,
        *,
        source_analysis: AnalysisResult,
        rewritten_text: str,
    ) -> EditorialQualityResult:
        rewritten_analysis = self._analyzer.analyze(rewritten_text)

        source_flag_count = len(source_analysis.flagged_segments)
        remaining_flag_count = len(rewritten_analysis.flagged_segments)
        removed_flag_count = max(
            source_flag_count - remaining_flag_count,
            0,
        )

        naturalness_score = self._calculate_naturalness_score(rewritten_analysis)

        warnings: list[str] = []

        if remaining_flag_count:
            warnings.append("The rewritten text still contains generic or formulaic language.")

        if naturalness_score < self._minimum_naturalness_score:
            warnings.append("The rewritten text did not meet the minimum naturalness threshold.")

        decision = EditorialQualityDecision.REVIEW if warnings else EditorialQualityDecision.PASS

        return EditorialQualityResult(
            decision=decision,
            naturalness_score=naturalness_score,
            source_flag_count=source_flag_count,
            remaining_flag_count=remaining_flag_count,
            removed_flag_count=removed_flag_count,
            remaining_flagged_segments=rewritten_analysis.flagged_segments,
            warnings=warnings,
        )

    @staticmethod
    def _calculate_naturalness_score(
        analysis: AnalysisResult,
    ) -> float:
        penalty = (
            analysis.scores.generic_language * 0.50
            + analysis.scores.transition_overuse * 0.25
            + analysis.scores.repetition * 0.15
            + analysis.scores.sentence_uniformity * 0.10
        )

        return round(max(0.0, min(1.0, 1.0 - penalty)), 3)
