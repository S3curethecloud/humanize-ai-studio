import json
from pathlib import Path

from app.evaluation.report_generator import (
    REPORT_SCHEMA_VERSION,
    build_evaluation_report,
    write_evaluation_report,
)


def test_report_contains_machine_readable_contract() -> None:
    report = build_evaluation_report()

    assert report["schema_version"] == (REPORT_SCHEMA_VERSION)

    corpus = report["corpus"]
    assert isinstance(corpus, dict)
    assert corpus["case_count"] == 7
    assert corpus["performance_case_count"] == 4
    assert corpus["safety_control_case_count"] == 3

    results = report["results"]
    assert isinstance(results, list)
    assert len(results) == 7

    cohorts = {result["cohort"] for result in results if isinstance(result, dict)}

    assert cohorts == {
        "performance",
        "safety_control",
    }


def test_performance_cohort_passes_release_thresholds() -> None:
    report = build_evaluation_report()

    summary = report["performance_summary"]
    assert isinstance(summary, dict)

    assert summary["total_cases"] == 4
    assert summary["provider_success_count"] == 4
    assert summary["repair_attempt_count"] == 1
    assert summary["repair_success_count"] == 1
    assert summary["fallback_count"] == 0
    assert summary["provider_success_rate"] == 1.0
    assert summary["repair_success_rate"] == 1.0
    assert summary["fallback_rate"] == 0.0

    release_gate = summary["release_gate"]
    assert isinstance(release_gate, dict)
    assert release_gate["passed"] is True


def test_safety_controls_fail_closed() -> None:
    report = build_evaluation_report()

    gate = report["safety_control_gate"]
    assert isinstance(gate, dict)

    assert gate["case_count"] == 3
    assert gate["controlled_fallback_count"] == 3
    assert gate["unsafe_output_release_count"] == 0
    assert gate["maximum_observed_model_call_count"] == 2
    assert gate["passed"] is True
    assert gate["failures"] == []


def test_combined_release_gate_passes() -> None:
    report = build_evaluation_report()

    release_gate = report["release_gate"]
    assert isinstance(release_gate, dict)

    assert release_gate["passed"] is True
    assert release_gate["failures"] == []


def test_write_evaluation_report_creates_json(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "evaluation" / "report.json"

    report = write_evaluation_report(
        output_path,
    )

    assert output_path.exists()

    saved_report = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved_report["schema_version"] == REPORT_SCHEMA_VERSION
    assert saved_report["release_gate"] == report["release_gate"]


def test_report_never_records_unsafe_release() -> None:
    report = build_evaluation_report()

    summary = report["overall_summary"]
    assert isinstance(summary, dict)

    assert summary["unsafe_output_release_count"] == 0
    assert summary["deep_structural_failure_release_count"] == 0
    assert summary["maximum_observed_model_call_count"] == 2
