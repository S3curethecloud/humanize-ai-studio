from app.domain.models import RewriteIntensity
from app.evaluation.quality_report import (
    EvaluationCaseResult,
)
from app.evaluation.safety_gate import (
    evaluate_safety_controls,
)


def _safe_fallback(
    case_id: str,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=case_id,
        intensity=(RewriteIntensity.DEEP_RECONSTRUCTION),
        provider_succeeded=False,
        repair_attempted=True,
        repair_succeeded=False,
        fallback_used=True,
        rejection_category=("structural_blueprint"),
        model_call_count=2,
        claim_integrity_preserved=True,
        useful_distance_satisfied=True,
        structural_blueprint_satisfied=False,
        unsafe_output_released=False,
    )


def test_safety_gate_accepts_controlled_fallbacks() -> None:
    gate = evaluate_safety_controls(
        (
            _safe_fallback("control-1"),
            _safe_fallback("control-2"),
        )
    )

    assert gate.passed is True
    assert gate.controlled_fallback_count == 2


def test_safety_gate_rejects_released_provider_output() -> None:
    result = EvaluationCaseResult(
        case_id="unsafe-provider-release",
        intensity=(RewriteIntensity.DEEP_RECONSTRUCTION),
        provider_succeeded=True,
        repair_attempted=True,
        repair_succeeded=True,
        fallback_used=False,
        rejection_category="none",
        model_call_count=2,
        claim_integrity_preserved=False,
        useful_distance_satisfied=True,
        structural_blueprint_satisfied=False,
        unsafe_output_released=True,
    )

    gate = evaluate_safety_controls((result,))

    assert gate.passed is False
    assert any("controlled_fallback_count" in failure for failure in gate.failures)
    assert any("unsafe_output_release_count" in failure for failure in gate.failures)


def test_safety_gate_rejects_third_model_call() -> None:
    result = EvaluationCaseResult(
        case_id="third-call",
        intensity=(RewriteIntensity.DEEP_RECONSTRUCTION),
        provider_succeeded=False,
        repair_attempted=True,
        repair_succeeded=False,
        fallback_used=True,
        rejection_category=("structural_blueprint"),
        model_call_count=3,
        claim_integrity_preserved=True,
        useful_distance_satisfied=True,
        structural_blueprint_satisfied=False,
        unsafe_output_released=False,
    )

    gate = evaluate_safety_controls((result,))

    assert gate.passed is False
    assert any("maximum_observed_model_call_count" in failure for failure in gate.failures)


def test_safety_gate_rejects_empty_control_set() -> None:
    gate = evaluate_safety_controls(())

    assert gate.passed is False
    assert gate.case_count == 0
