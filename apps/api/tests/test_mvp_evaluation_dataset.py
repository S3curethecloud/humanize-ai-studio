from pathlib import Path

from app.evaluation.runner import load_evaluation_cases


def test_mvp_baseline_dataset_is_valid() -> None:
    dataset_path = Path(__file__).parents[3] / "evals" / "datasets" / "mvp_baseline.jsonl"

    cases = load_evaluation_cases(dataset_path)

    assert len(cases) == 6
    assert len({case.case_id for case in cases}) == 6
