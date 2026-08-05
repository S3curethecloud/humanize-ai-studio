from app.domain.models import RewriteIntensity
from app.evaluation.corpus import (
    default_evaluation_corpus,
)


def test_default_corpus_has_unique_case_ids() -> None:
    corpus = default_evaluation_corpus()
    case_ids = tuple(case.case_id for case in corpus)

    assert len(case_ids) == len(set(case_ids))


def test_default_corpus_covers_all_intensities() -> None:
    corpus = default_evaluation_corpus()
    intensities = {case.intensity for case in corpus}

    assert intensities == {
        RewriteIntensity.LIGHT_EDIT,
        RewriteIntensity.NATURAL_REWRITE,
        RewriteIntensity.DEEP_RECONSTRUCTION,
    }


def test_default_corpus_covers_controlled_failure_categories() -> None:
    corpus = default_evaluation_corpus()
    categories = {case.expected_rejection_category for case in corpus}

    assert "claim_integrity" in categories
    assert "useful_distance" in categories
    assert "structural_blueprint" in categories


def test_default_corpus_never_requires_more_than_two_calls() -> None:
    corpus = default_evaluation_corpus()

    assert max(case.expected_model_call_count for case in corpus) == 2


def test_default_corpus_has_expected_cohort_sizes() -> None:
    corpus = default_evaluation_corpus()

    performance_cases = tuple(case for case in corpus if case.cohort == "performance")
    safety_cases = tuple(case for case in corpus if case.cohort == "safety_control")

    assert len(performance_cases) == 4
    assert len(safety_cases) == 3


def test_safety_control_cases_expect_fallback() -> None:
    corpus = default_evaluation_corpus()

    safety_cases = tuple(case for case in corpus if case.cohort == "safety_control")

    assert all(case.expected_fallback_used for case in safety_cases)
    assert all(not case.expected_provider_success for case in safety_cases)
