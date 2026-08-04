from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from app.core.settings import Settings
from app.domain.models import RewriteRequest
from app.evaluation.models import (
    CategoryEvaluationSummary,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationReport,
    EvaluationSummary,
)
from app.evaluation.text_normalization import normalize_evaluation_text
from app.providers.base import RewriteProvider
from app.providers.registry import build_rewrite_provider
from app.workflows.rewrite_workflow import RewriteWorkflow


class EvaluationDatasetError(ValueError):
    """Raised when an evaluation dataset cannot be loaded."""


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    if not path.is_file():
        raise EvaluationDatasetError(f"Evaluation dataset does not exist: {path}")

    cases: list[EvaluationCase] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = raw_line.strip()

        if not stripped:
            continue

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise EvaluationDatasetError(f"Invalid JSON on line {line_number} of {path}.") from exc

        try:
            evaluation_case = EvaluationCase.model_validate(payload)
        except ValidationError as exc:
            raise EvaluationDatasetError(
                f"Invalid evaluation case on line {line_number} of {path}: {exc}"
            ) from exc

        cases.append(evaluation_case)

    if not cases:
        raise EvaluationDatasetError(f"Evaluation dataset contains no cases: {path}")

    case_ids = [case.case_id for case in cases]

    if len(case_ids) != len(set(case_ids)):
        raise EvaluationDatasetError("Evaluation case IDs must be unique.")

    return cases


class BatchEvaluationRunner:
    def __init__(
        self,
        *,
        provider: RewriteProvider,
        input_cost_per_million_tokens_usd: float | None = None,
        output_cost_per_million_tokens_usd: float | None = None,
    ) -> None:
        self._workflow = RewriteWorkflow(provider=provider)
        self._input_cost = _validate_optional_cost(
            input_cost_per_million_tokens_usd,
            "input_cost_per_million_tokens_usd",
        )
        self._output_cost = _validate_optional_cost(
            output_cost_per_million_tokens_usd,
            "output_cost_per_million_tokens_usd",
        )

    def run(
        self,
        *,
        dataset_path: Path,
        cases: Iterable[EvaluationCase],
    ) -> EvaluationReport:
        results = [self._evaluate_case(case) for case in cases]

        if not results:
            raise ValueError("At least one evaluation case is required.")

        first = results[0]
        summary = self._summarize(results)

        return EvaluationReport(
            dataset_path=str(dataset_path),
            provider_name=first.provider_name,
            model_name=first.model_name,
            prompt_version=first.prompt_version,
            input_cost_per_million_tokens_usd=self._input_cost,
            output_cost_per_million_tokens_usd=self._output_cost,
            summary=summary,
            cases=results,
        )

    def _evaluate_case(
        self,
        case: EvaluationCase,
    ) -> EvaluationCaseResult:
        response = self._workflow.execute(
            RewriteRequest(
                text=case.source_text,
                document_type=case.document_type,
                audience=case.audience,
                tone=case.tone,
                intensity=case.intensity,
            ),
            trace_id=f"eval_{case.case_id}",
        )

        normalized_rewrite = normalize_evaluation_text(response.rewritten_text)

        expected_present = all(
            normalize_evaluation_text(expected) in normalized_rewrite
            for expected in case.expected_substrings
        )

        expected_groups_present = all(
            any(
                normalize_evaluation_text(alternative) in normalized_rewrite
                for alternative in group
            )
            for group in case.expected_substring_groups
        )

        exact_preservation_present = all(
            normalize_evaluation_text(expected) in normalized_rewrite
            for expected in case.exact_preservation_substrings
        )

        forbidden_absent = all(
            normalize_evaluation_text(forbidden) not in normalized_rewrite
            for forbidden in case.forbidden_substrings
        )

        failure_reasons: list[str] = []

        if response.verification.decision.value != case.expected_factual_decision:
            failure_reasons.append("Factual decision did not match the expected result.")

        if response.editorial_quality.decision.value != case.expected_editorial_decision:
            failure_reasons.append("Editorial decision did not match the expected result.")

        if not expected_present:
            failure_reasons.append("One or more expected substrings were missing.")

        if not expected_groups_present:
            failure_reasons.append("One or more expected alternative groups were missing.")

        if not exact_preservation_present:
            failure_reasons.append("One or more exact-preservation substrings were missing.")

        if not forbidden_absent:
            failure_reasons.append("One or more forbidden substrings remained.")

        accepted = not failure_reasons

        usage = response.provider_execution.usage

        estimated_cost = _estimate_cost(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            input_cost_per_million_tokens_usd=self._input_cost,
            output_cost_per_million_tokens_usd=self._output_cost,
        )

        return EvaluationCaseResult(
            case_id=case.case_id,
            category=case.category,
            risk_tags=case.risk_tags,
            description=case.description,
            accepted=accepted,
            trace_id=response.trace_id,
            provider_name=response.provider_name,
            model_name=response.model_name,
            prompt_version=response.prompt_version,
            factual_decision=response.verification.decision.value,
            editorial_decision=response.editorial_quality.decision.value,
            final_workflow_state=response.workflow_states[-1].value,
            expected_substrings_present=expected_present,
            forbidden_substrings_absent=forbidden_absent,
            fallback_used=response.provider_execution.fallback_used,
            latency_ms=response.provider_execution.latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=estimated_cost,
            rewritten_text=response.rewritten_text,
            failure_reasons=failure_reasons,
        )

    def _summarize(
        self,
        results: list[EvaluationCaseResult],
    ) -> EvaluationSummary:
        total_cases = len(results)
        accepted_cases = sum(result.accepted for result in results)
        factual_passes = sum(result.factual_decision == "pass" for result in results)
        editorial_passes = sum(result.editorial_decision == "pass" for result in results)
        fallbacks = sum(result.fallback_used for result in results)

        total_input_tokens = sum(result.input_tokens or 0 for result in results)
        total_output_tokens = sum(result.output_tokens or 0 for result in results)
        total_tokens = sum(result.total_tokens or 0 for result in results)

        average_latency_ms = round(
            sum(result.latency_ms for result in results) / total_cases,
            3,
        )

        cost_values = [
            result.estimated_cost_usd for result in results if result.estimated_cost_usd is not None
        ]

        estimated_total_cost: float | None

        if len(cost_values) == total_cases:
            estimated_total_cost = round(sum(cost_values), 9)
        else:
            estimated_total_cost = None

        cost_per_accepted: float | None

        if estimated_total_cost is not None and accepted_cases > 0:
            cost_per_accepted = round(
                estimated_total_cost / accepted_cases,
                9,
            )
        else:
            cost_per_accepted = None

        return EvaluationSummary(
            total_cases=total_cases,
            accepted_cases=accepted_cases,
            acceptance_rate=round(accepted_cases / total_cases, 3),
            factual_pass_rate=round(factual_passes / total_cases, 3),
            editorial_pass_rate=round(editorial_passes / total_cases, 3),
            fallback_rate=round(fallbacks / total_cases, 3),
            average_latency_ms=average_latency_ms,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tokens=total_tokens,
            estimated_total_cost_usd=estimated_total_cost,
            cost_per_accepted_rewrite_usd=cost_per_accepted,
            by_category=_summarize_categories(results),
        )


def _summarize_categories(
    results: list[EvaluationCaseResult],
) -> dict[str, CategoryEvaluationSummary]:
    grouped: dict[str, list[EvaluationCaseResult]] = {}

    for result in results:
        grouped.setdefault(result.category, []).append(result)

    summaries: dict[str, CategoryEvaluationSummary] = {}

    for category, category_results in sorted(grouped.items()):
        total = len(category_results)
        accepted = sum(result.accepted for result in category_results)
        factual_passes = sum(result.factual_decision == "pass" for result in category_results)
        editorial_passes = sum(result.editorial_decision == "pass" for result in category_results)

        summaries[category] = CategoryEvaluationSummary(
            total_cases=total,
            accepted_cases=accepted,
            acceptance_rate=round(accepted / total, 3),
            factual_pass_rate=round(factual_passes / total, 3),
            editorial_pass_rate=round(editorial_passes / total, 3),
        )

    return summaries


def _validate_optional_cost(
    value: float | None,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    if value < 0:
        raise ValueError(f"{field_name} must not be negative.")

    return value


def _estimate_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    input_cost_per_million_tokens_usd: float | None,
    output_cost_per_million_tokens_usd: float | None,
) -> float | None:
    if (
        input_tokens is None
        or output_tokens is None
        or input_cost_per_million_tokens_usd is None
        or output_cost_per_million_tokens_usd is None
    ):
        return None

    input_cost = (input_tokens / 1_000_000) * input_cost_per_million_tokens_usd

    output_cost = (output_tokens / 1_000_000) * output_cost_per_million_tokens_usd

    return round(input_cost + output_cost, 9)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the HumanizeAI Studio batch evaluation suite."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Path to a JSONL evaluation dataset.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the JSON evaluation report will be written.",
    )
    parser.add_argument(
        "--input-cost-per-million",
        type=float,
        default=None,
        help="Optional input-token price per million tokens in USD.",
    )
    parser.add_argument(
        "--output-cost-per-million",
        type=float,
        default=None,
        help="Optional output-token price per million tokens in USD.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    settings = Settings.from_environment()
    provider = build_rewrite_provider(settings)
    cases = load_evaluation_cases(args.dataset)

    runner = BatchEvaluationRunner(
        provider=provider,
        input_cost_per_million_tokens_usd=(args.input_cost_per_million),
        output_cost_per_million_tokens_usd=(args.output_cost_per_million),
    )

    report = runner.run(
        dataset_path=args.dataset,
        cases=cases,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            report.summary.model_dump(),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
