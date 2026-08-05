from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.corpus import (
    default_evaluation_corpus,
)
from app.evaluation.evaluator import evaluate_case
from app.evaluation.quality_report import (
    EvaluationReleaseThresholds,
    summarize_evaluation,
)
from app.evaluation.safety_gate import (
    evaluate_safety_controls,
)

REPORT_SCHEMA_VERSION = "humanize-evaluation-v2"


def build_evaluation_report(
    *,
    thresholds: EvaluationReleaseThresholds | None = None,
) -> dict[str, object]:
    active_thresholds = thresholds or EvaluationReleaseThresholds()
    corpus = default_evaluation_corpus()

    evaluated = tuple(
        (
            case,
            evaluate_case(case),
        )
        for case in corpus
    )

    all_results = tuple(result for _, result in evaluated)
    performance_results = tuple(
        result for case, result in evaluated if case.cohort == "performance"
    )
    safety_control_results = tuple(
        result for case, result in evaluated if case.cohort == "safety_control"
    )

    overall_summary = summarize_evaluation(
        all_results,
        active_thresholds,
    )
    performance_summary = summarize_evaluation(
        performance_results,
        active_thresholds,
    )
    safety_control_gate = evaluate_safety_controls(
        safety_control_results,
    )

    release_failures = performance_summary.release_gate.failures + safety_control_gate.failures

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus": {
            "name": ("default-deterministic-quality-corpus"),
            "case_count": len(corpus),
            "performance_case_count": len(performance_results),
            "safety_control_case_count": len(safety_control_results),
            "case_ids": [case.case_id for case in corpus],
        },
        "thresholds": asdict(active_thresholds),
        "results": [
            {
                **result.to_dict(),
                "cohort": case.cohort,
            }
            for case, result in evaluated
        ],
        "overall_summary": (overall_summary.to_dict()),
        "performance_summary": (performance_summary.to_dict()),
        "safety_control_gate": (safety_control_gate.to_dict()),
        "release_gate": {
            "passed": not release_failures,
            "failures": list(release_failures),
        },
    }


def write_evaluation_report(
    output_path: Path,
    *,
    thresholds: EvaluationReleaseThresholds | None = None,
) -> dict[str, object]:
    report = build_evaluation_report(
        thresholds=thresholds,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return report
