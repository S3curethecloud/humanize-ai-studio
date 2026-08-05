from app.evaluation.corpus import (
    default_evaluation_corpus,
)
from app.evaluation.evaluator import evaluate_case
from app.evaluation.quality_report import (
    summarize_evaluation,
)


def test_evaluator_matches_expected_case_outcomes() -> None:
    corpus = default_evaluation_corpus()

    for case in corpus:
        result = evaluate_case(case)

        assert result.provider_succeeded is (case.expected_provider_success)
        assert result.repair_attempted is (case.expected_repair_attempted)
        assert result.repair_succeeded is (case.expected_repair_succeeded)
        assert result.fallback_used is (case.expected_fallback_used)
        assert result.rejection_category == (case.expected_rejection_category)
        assert result.model_call_count == (case.expected_model_call_count)
        assert result.claim_integrity_preserved is (case.expected_claim_integrity_preserved)
        assert result.useful_distance_satisfied is (case.expected_useful_distance_satisfied)
        assert result.structural_blueprint_satisfied is (
            case.expected_structural_blueprint_satisfied
        )
        assert result.unsafe_output_released is False


def test_default_corpus_produces_expected_summary() -> None:
    results = tuple(evaluate_case(case) for case in default_evaluation_corpus())

    summary = summarize_evaluation(results)

    assert summary.total_cases == 7
    assert summary.provider_success_count == 4
    assert summary.repair_attempt_count == 4
    assert summary.repair_success_count == 1
    assert summary.fallback_count == 3
    assert summary.claim_integrity_rejection_count == 1
    assert summary.useful_distance_rejection_count == 1
    assert summary.structural_blueprint_rejection_count == 1
    assert summary.maximum_observed_model_call_count == 2


def test_default_corpus_does_not_release_unsafe_output() -> None:
    results = tuple(evaluate_case(case) for case in default_evaluation_corpus())

    summary = summarize_evaluation(results)

    assert summary.unsafe_output_release_count == 0
    assert summary.deep_structural_failure_release_count == 0
