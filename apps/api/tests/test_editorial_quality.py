from app.domain.models import EditorialQualityDecision
from app.services.editorial_quality import EditorialQualityEvaluator
from app.services.pattern_analyzer import PatternAnalyzer


def test_quality_passes_when_formulaic_language_is_removed() -> None:
    analyzer = PatternAnalyzer()
    evaluator = EditorialQualityEvaluator(analyzer=analyzer)

    source = "Furthermore, it is important to note that the migration completed in 30 days."
    rewritten = "The migration completed in 30 days."

    result = evaluator.evaluate(
        source_analysis=analyzer.analyze(source),
        rewritten_text=rewritten,
    )

    assert result.decision is EditorialQualityDecision.PASS
    assert result.source_flag_count == 2
    assert result.remaining_flag_count == 0
    assert result.removed_flag_count == 2
    assert result.naturalness_score >= 0.75
    assert result.warnings == []


def test_quality_requires_review_when_generic_language_remains() -> None:
    analyzer = PatternAnalyzer()
    evaluator = EditorialQualityEvaluator(analyzer=analyzer)

    source = (
        "In today's rapidly evolving technological landscape, "
        "it is important to note that the migration completed."
    )
    rewritten = "In today's rapidly evolving technological landscape, the migration completed."

    result = evaluator.evaluate(
        source_analysis=analyzer.analyze(source),
        rewritten_text=rewritten,
    )

    assert result.decision is EditorialQualityDecision.REVIEW
    assert result.source_flag_count == 2
    assert result.remaining_flag_count == 1
    assert result.removed_flag_count == 1
    assert result.naturalness_score < 0.75
    assert result.warnings


def test_quality_detects_generic_phrase_with_smart_apostrophe() -> None:
    analyzer = PatternAnalyzer()
    evaluator = EditorialQualityEvaluator(analyzer=analyzer)

    source = "In today's rapidly evolving technological landscape, the migration completed."
    rewritten = "In today’s rapidly evolving technological landscape, the migration completed."

    result = evaluator.evaluate(
        source_analysis=analyzer.analyze(source),
        rewritten_text=rewritten,
    )

    assert result.decision is EditorialQualityDecision.REVIEW
    assert result.remaining_flag_count == 1
    assert result.remaining_flagged_segments[0].text.startswith("In today")
