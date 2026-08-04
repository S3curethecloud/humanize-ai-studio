from collections import Counter
from pathlib import Path

from app.evaluation.runner import load_evaluation_cases


def test_expanded_baseline_contains_40_unique_cases() -> None:
    dataset_path = Path(__file__).parents[3] / "evals" / "datasets" / "expanded_baseline_40.jsonl"

    cases = load_evaluation_cases(dataset_path)

    assert len(cases) == 40
    assert len({case.case_id for case in cases}) == 40


def test_expanded_baseline_has_category_coverage() -> None:
    dataset_path = Path(__file__).parents[3] / "evals" / "datasets" / "expanded_baseline_40.jsonl"

    cases = load_evaluation_cases(dataset_path)
    categories = Counter(case.category for case in cases)

    assert len(categories) >= 8
    assert categories["technical_architecture"] >= 5
    assert categories["interview_answer"] >= 5
    assert categories["professional_email"] >= 5


def test_expanded_baseline_has_high_risk_cases() -> None:
    dataset_path = Path(__file__).parents[3] / "evals" / "datasets" / "expanded_baseline_40.jsonl"

    cases = load_evaluation_cases(dataset_path)

    all_tags = {tag for case in cases for tag in case.risk_tags}

    assert "negation" in all_tags
    assert "multiple_numbers" in all_tags
    assert "citations" in all_tags
    assert "mandatory_language" in all_tags
    assert "identity" in all_tags
