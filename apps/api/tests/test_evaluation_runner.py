import json
from pathlib import Path

import pytest

from app.evaluation.models import EvaluationCase
from app.evaluation.runner import (
    BatchEvaluationRunner,
    EvaluationDatasetError,
    load_evaluation_cases,
)
from app.providers.deterministic import DeterministicRewriteProvider


def test_load_evaluation_cases_reads_jsonl(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "case_id": "case-001",
                "description": "Test case",
                "source_text": "Furthermore, the migration took 30 days.",
                "expected_substrings": ["30 days"],
                "forbidden_substrings": ["furthermore"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_evaluation_cases(dataset)

    assert len(cases) == 1
    assert cases[0].case_id == "case-001"


def test_load_evaluation_cases_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset.jsonl"

    record = json.dumps(
        {
            "case_id": "duplicate",
            "description": "Duplicate case",
            "source_text": "The migration completed.",
        }
    )

    dataset.write_text(
        f"{record}\n{record}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationDatasetError,
        match="must be unique",
    ):
        load_evaluation_cases(dataset)


def test_batch_runner_calculates_acceptance_and_cost() -> None:
    runner = BatchEvaluationRunner(
        provider=DeterministicRewriteProvider(),
        input_cost_per_million_tokens_usd=0.20,
        output_cost_per_million_tokens_usd=0.30,
    )

    cases = [
        EvaluationCase(
            case_id="case-001",
            description="Remove formulaic language",
            source_text=(
                "Furthermore, it is important to note that the migration completed in 30 days."
            ),
            expected_substrings=["30 days"],
            forbidden_substrings=[
                "furthermore",
                "it is important to note",
            ],
        )
    ]

    report = runner.run(
        dataset_path=Path("in-memory.jsonl"),
        cases=cases,
    )

    assert report.summary.total_cases == 1
    assert report.summary.accepted_cases == 1
    assert report.summary.acceptance_rate == 1.0
    assert report.summary.factual_pass_rate == 1.0
    assert report.summary.editorial_pass_rate == 1.0
    assert report.summary.fallback_rate == 0.0
    assert report.summary.total_tokens == 0
    assert report.summary.estimated_total_cost_usd == 0.0
    assert report.summary.cost_per_accepted_rewrite_usd == 0.0
    assert report.cases[0].accepted is True


def test_batch_runner_rejects_case_when_forbidden_phrase_remains() -> None:
    runner = BatchEvaluationRunner(
        provider=DeterministicRewriteProvider(),
    )

    cases = [
        EvaluationCase(
            case_id="case-002",
            description="Forbidden phrase remains",
            source_text="The migration completed in 30 days.",
            expected_substrings=["30 days"],
            forbidden_substrings=["migration"],
        )
    ]

    report = runner.run(
        dataset_path=Path("in-memory.jsonl"),
        cases=cases,
    )

    assert report.summary.total_cases == 1
    assert report.summary.accepted_cases == 0
    assert report.summary.acceptance_rate == 0.0
    assert report.cases[0].accepted is False
    assert report.cases[0].failure_reasons == ["One or more forbidden substrings remained."]


def test_batch_runner_calculates_category_summaries() -> None:
    runner = BatchEvaluationRunner(
        provider=DeterministicRewriteProvider(),
    )

    cases = [
        EvaluationCase(
            case_id="email-001",
            category="professional_email",
            description="Email case",
            source_text="Furthermore, the migration completed in 30 days.",
            expected_substrings=["30 days"],
            forbidden_substrings=["furthermore"],
        ),
        EvaluationCase(
            case_id="architecture-001",
            category="technical_architecture",
            description="Architecture case",
            source_text="Additionally, the gateway validates identity context.",
            expected_substrings=["identity context"],
            forbidden_substrings=["additionally"],
        ),
    ]

    report = runner.run(
        dataset_path=Path("in-memory.jsonl"),
        cases=cases,
    )

    assert report.summary.by_category["professional_email"].total_cases == 1
    assert report.summary.by_category["professional_email"].acceptance_rate == 1.0
    assert report.summary.by_category["technical_architecture"].acceptance_rate == 1.0


def test_batch_runner_accepts_normalized_unicode_equivalence() -> None:
    runner = BatchEvaluationRunner(
        provider=DeterministicRewriteProvider(),
    )

    cases = [
        EvaluationCase(
            case_id="unicode-001",
            category="customer_support",
            description="Normalize Unicode date spacing",
            source_text="Please respond by August 8, 2026.",
            expected_substrings=["August 8, 2026"],
        )
    ]

    report = runner.run(
        dataset_path=Path("in-memory.jsonl"),
        cases=cases,
    )

    assert report.cases[0].accepted is True


def test_batch_runner_accepts_expected_alternative_group() -> None:
    runner = BatchEvaluationRunner(
        provider=DeterministicRewriteProvider(),
    )

    cases = [
        EvaluationCase(
            case_id="alternative-001",
            category="interview_answer",
            description="Accept equivalent achievement wording",
            source_text="I reduced deployment time by 40%.",
            expected_substring_groups=[
                [
                    "reduced deployment time",
                    "cut deployment time",
                ]
            ],
            exact_preservation_substrings=["40%"],
        )
    ]

    report = runner.run(
        dataset_path=Path("in-memory.jsonl"),
        cases=cases,
    )

    assert report.cases[0].accepted is True
