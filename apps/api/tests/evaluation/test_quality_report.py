from app.domain.models import RewriteIntensity
from app.evaluation.quality_report import (
    EvaluationCaseResult,
    EvaluationReleaseThresholds,
    RejectionCategory,
    summarize_evaluation,
)


def _result(
    *,
    case_id: str,
    intensity: RewriteIntensity,
    provider_succeeded: bool = True,
    repair_attempted: bool = False,
    repair_succeeded: bool = False,
    fallback_used: bool = False,
    rejection_category: RejectionCategory = "none",
    model_call_count: int = 1,
    claim_integrity_preserved: bool = True,
    useful_distance_satisfied: bool = True,
    structural_blueprint_satisfied: bool = True,
    unsafe_output_released: bool = False,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=case_id,
        intensity=intensity,
        provider_succeeded=provider_succeeded,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
        fallback_used=fallback_used,
        rejection_category=rejection_category,
        model_call_count=model_call_count,
        claim_integrity_preserved=claim_integrity_preserved,
        useful_distance_satisfied=useful_distance_satisfied,
        structural_blueprint_satisfied=(structural_blueprint_satisfied),
        unsafe_output_released=unsafe_output_released,
    )


def test_evaluation_summary_reports_release_metrics() -> None:
    results = (
        _result(
            case_id="light-direct",
            intensity=RewriteIntensity.LIGHT_EDIT,
        ),
        _result(
            case_id="natural-direct",
            intensity=RewriteIntensity.NATURAL_REWRITE,
        ),
        _result(
            case_id="deep-repair",
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            repair_attempted=True,
            repair_succeeded=True,
            model_call_count=2,
        ),
        _result(
            case_id="deep-safe-terminal",
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            provider_succeeded=False,
            repair_attempted=True,
            fallback_used=True,
            rejection_category="structural_blueprint",
            model_call_count=2,
            structural_blueprint_satisfied=False,
        ),
    )

    summary = summarize_evaluation(
        results,
        EvaluationReleaseThresholds(
            minimum_provider_success_rate=0.70,
            minimum_repair_success_rate=0.50,
            maximum_fallback_rate=0.30,
        ),
    )

    assert summary.total_cases == 4
    assert summary.provider_success_count == 3
    assert summary.repair_attempt_count == 2
    assert summary.repair_success_count == 1
    assert summary.fallback_count == 1
    assert summary.structural_blueprint_rejection_count == 1
    assert summary.maximum_observed_model_call_count == 2
    assert summary.provider_success_rate == 0.75
    assert summary.repair_attempt_rate == 0.50
    assert summary.repair_success_rate == 0.50
    assert summary.fallback_rate == 0.25
    assert summary.release_gate.passed is True
    assert summary.release_gate.failures == ()


def test_release_gate_rejects_excessive_fallback_rate() -> None:
    results = (
        _result(
            case_id="fallback-1",
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            provider_succeeded=False,
            fallback_used=True,
            rejection_category="provider_response",
        ),
        _result(
            case_id="success-1",
            intensity=RewriteIntensity.NATURAL_REWRITE,
        ),
    )

    summary = summarize_evaluation(
        results,
        EvaluationReleaseThresholds(
            minimum_provider_success_rate=0.50,
            maximum_fallback_rate=0.25,
        ),
    )

    assert summary.release_gate.passed is False
    assert any("fallback_rate" in failure for failure in summary.release_gate.failures)


def test_release_gate_rejects_third_model_call() -> None:
    results = (
        _result(
            case_id="third-call",
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            repair_attempted=True,
            repair_succeeded=True,
            model_call_count=3,
        ),
    )

    summary = summarize_evaluation(results)

    assert summary.release_gate.passed is False
    assert any(
        "maximum_observed_model_call_count" in failure for failure in summary.release_gate.failures
    )


def test_release_gate_rejects_unsafe_output_release() -> None:
    results = (
        _result(
            case_id="unsafe-release",
            intensity=RewriteIntensity.NATURAL_REWRITE,
            claim_integrity_preserved=False,
            unsafe_output_released=True,
        ),
    )

    summary = summarize_evaluation(results)

    assert summary.unsafe_output_release_count == 1
    assert summary.release_gate.passed is False
    assert any(
        "unsafe_output_release_count" in failure for failure in summary.release_gate.failures
    )


def test_release_gate_rejects_deep_structural_failure_release() -> None:
    results = (
        _result(
            case_id="lexical-only-deep",
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            structural_blueprint_satisfied=False,
        ),
    )

    summary = summarize_evaluation(results)

    assert summary.deep_structural_failure_release_count == 1
    assert summary.release_gate.passed is False
    assert any(
        "deep_structural_failure_release_count" in failure
        for failure in summary.release_gate.failures
    )


def test_empty_evaluation_fails_provider_success_threshold() -> None:
    summary = summarize_evaluation(())

    assert summary.total_cases == 0
    assert summary.provider_success_rate == 0.0
    assert summary.release_gate.passed is False
