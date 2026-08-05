from __future__ import annotations

from app.evaluation.corpus import EvaluationCase
from app.evaluation.quality_report import (
    EvaluationCaseResult,
    RejectionCategory,
)
from app.providers.claim_integrity import (
    find_claim_integrity_violations,
)
from app.providers.rewrite_distance import (
    evaluate_rewrite_distance,
    follows_deep_repair_blueprint,
)


def evaluate_case(
    case: EvaluationCase,
) -> EvaluationCaseResult:
    model_call_count = 1
    repair_attempted = False
    repair_succeeded = False
    rejection_category: RejectionCategory = "none"

    initial_violations = find_claim_integrity_violations(
        source_text=case.source_text,
        rewritten_text=case.initial_output,
    )

    selected_output = case.initial_output

    if initial_violations:
        repair_attempted = True
        model_call_count = 2

        if case.repair_output is None:
            rejection_category = "provider_response"
            return _fallback_result(
                case=case,
                repair_attempted=repair_attempted,
                rejection_category=rejection_category,
                model_call_count=model_call_count,
                claim_integrity_preserved=False,
                useful_distance_satisfied=False,
                structural_blueprint_satisfied=False,
            )

        selected_output = case.repair_output

        repaired_violations = find_claim_integrity_violations(
            source_text=case.source_text,
            rewritten_text=selected_output,
        )

        if repaired_violations:
            rejection_category = "claim_integrity"
            return _fallback_result(
                case=case,
                repair_attempted=repair_attempted,
                rejection_category=rejection_category,
                model_call_count=model_call_count,
                claim_integrity_preserved=False,
                useful_distance_satisfied=False,
                structural_blueprint_satisfied=(case.intensity.value != "deep_reconstruction"),
            )

    distance = evaluate_rewrite_distance(
        source_text=case.source_text,
        rewritten_text=selected_output,
        intensity=case.intensity,
    )

    if not distance.acceptable:
        rejection_category = "useful_distance"
        return _fallback_result(
            case=case,
            repair_attempted=repair_attempted,
            rejection_category=rejection_category,
            model_call_count=model_call_count,
            claim_integrity_preserved=True,
            useful_distance_satisfied=False,
            structural_blueprint_satisfied=(case.intensity.value != "deep_reconstruction"),
        )

    structural_blueprint_satisfied = True

    if case.intensity.value == "deep_reconstruction" and repair_attempted:
        structural_blueprint_satisfied = follows_deep_repair_blueprint(
            source_text=case.source_text,
            rewritten_text=selected_output,
        )

        if not structural_blueprint_satisfied:
            rejection_category = "structural_blueprint"
            return _fallback_result(
                case=case,
                repair_attempted=repair_attempted,
                rejection_category=rejection_category,
                model_call_count=model_call_count,
                claim_integrity_preserved=True,
                useful_distance_satisfied=True,
                structural_blueprint_satisfied=False,
            )

    if repair_attempted:
        repair_succeeded = True

    return EvaluationCaseResult(
        case_id=case.case_id,
        intensity=case.intensity,
        provider_succeeded=True,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
        fallback_used=False,
        rejection_category="none",
        model_call_count=model_call_count,
        claim_integrity_preserved=True,
        useful_distance_satisfied=True,
        structural_blueprint_satisfied=(structural_blueprint_satisfied),
        unsafe_output_released=False,
    )


def _fallback_result(
    *,
    case: EvaluationCase,
    repair_attempted: bool,
    rejection_category: RejectionCategory,
    model_call_count: int,
    claim_integrity_preserved: bool,
    useful_distance_satisfied: bool,
    structural_blueprint_satisfied: bool,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=case.case_id,
        intensity=case.intensity,
        provider_succeeded=False,
        repair_attempted=repair_attempted,
        repair_succeeded=False,
        fallback_used=True,
        rejection_category=rejection_category,
        model_call_count=model_call_count,
        claim_integrity_preserved=claim_integrity_preserved,
        useful_distance_satisfied=(useful_distance_satisfied),
        structural_blueprint_satisfied=(structural_blueprint_satisfied),
        unsafe_output_released=False,
    )
