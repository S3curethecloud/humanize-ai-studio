from __future__ import annotations

from collections import defaultdict
from typing import Protocol

from app.v2.domain.eval_dataset import (
    EvaluationDataset,
    EvaluationDatasetCase,
)
from app.v2.domain.eval_execution import (
    EvaluationCaseExecutionResult,
    EvaluationRunRequest,
)
from app.v2.domain.eval_ops import (
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.repositories.eval_dataset import (
    EvaluationDatasetRepository,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
)
from app.v2.services.eval_metric_service import (
    DeterministicEvaluationMetricService,
    EvaluationMetricEvidenceUnavailableError,
)


class EvaluationRunDatasetResolutionError(
    RuntimeError
):
    pass


class EvaluationRunExecutionIntegrityError(
    RuntimeError
):
    pass


class EvaluationCaseExecutor(Protocol):
    def execute(
        self,
        *,
        case: EvaluationDatasetCase,
        target_id: str,
    ) -> EvaluationCaseExecutionResult: ...


class EvaluationRunExecutionService:
    def __init__(
        self,
        *,
        datasets: EvaluationDatasetRepository,
        runs: EvaluationRunRepository,
        case_executor: EvaluationCaseExecutor,
        metrics: DeterministicEvaluationMetricService,
    ) -> None:
        self._datasets = datasets
        self._runs = runs
        self._case_executor = case_executor
        self._metrics = metrics

    def execute(
        self,
        request: EvaluationRunRequest,
    ) -> EvaluationRunRecord:
        dataset = self._resolve_dataset(request)

        values_by_metric: dict[
            EvaluationMetric,
            list[float],
        ] = defaultdict(list)

        failed_case_count = 0
        incomplete_metrics: set[
            EvaluationMetric
        ] = set()

        for case in dataset.cases:
            result = self._case_executor.execute(
                case=case,
                target_id=request.target_id,
            )

            self._require_case_result_integrity(
                request=request,
                case=case,
                result=result,
            )

            evidence = result.evidence

            if evidence.provider_error:
                failed_case_count += 1

            for metric in request.metrics:
                if (
                    evidence.provider_error
                    and metric
                    is not EvaluationMetric.PROVIDER_ERROR_RATE
                ):
                    incomplete_metrics.add(metric)
                    continue

                try:
                    measurement = self._metrics.evaluate(
                        case=case,
                        evidence=evidence,
                        metric=metric,
                    )
                except EvaluationMetricEvidenceUnavailableError:
                    incomplete_metrics.add(metric)
                    continue

                values_by_metric[metric].append(
                    measurement.result.value
                )

        case_count = len(dataset.cases)

        complete_results = tuple(
            EvaluationMetricResult(
                metric=metric,
                value=_mean(
                    values_by_metric[metric]
                ),
            )
            for metric in request.metrics
            if (
                metric not in incomplete_metrics
                and len(values_by_metric[metric])
                == case_count
            )
        )

        run_failed = (
            failed_case_count > 0
            or bool(incomplete_metrics)
            or len(complete_results) != len(request.metrics)
        )

        record = EvaluationRunRecord(
            identity=EvaluationRunIdentity(
                run_id=request.run_id,
                dataset=request.dataset,
                target_id=request.target_id,
            ),
            outcome=(
                EvaluationRunOutcome.FAILED
                if run_failed
                else EvaluationRunOutcome.SUCCEEDED
            ),
            evaluated_case_count=case_count,
            failed_case_count=failed_case_count,
            metric_results=complete_results,
            failure_reason=(
                _failure_reason(
                    failed_case_count=failed_case_count,
                    incomplete_metrics=incomplete_metrics,
                )
                if run_failed
                else None
            ),
        )

        return self._runs.create(record)

    def _resolve_dataset(
        self,
        request: EvaluationRunRequest,
    ) -> EvaluationDataset:
        try:
            dataset = self._datasets.get(
                request.dataset
            )
        except Exception as exc:
            raise EvaluationRunDatasetResolutionError(
                "evaluation dataset lookup failed"
            ) from exc

        if dataset is None:
            raise EvaluationRunDatasetResolutionError(
                "evaluation dataset does not exist: "
                f"{request.dataset.dataset_id}:"
                f"{request.dataset.dataset_version}"
            )

        if dataset.identity != request.dataset:
            raise EvaluationRunDatasetResolutionError(
                "evaluation dataset repository returned "
                "a different dataset identity"
            )

        return dataset

    @staticmethod
    def _require_case_result_integrity(
        *,
        request: EvaluationRunRequest,
        case: EvaluationDatasetCase,
        result: EvaluationCaseExecutionResult,
    ) -> None:
        if result.target_id != request.target_id:
            raise EvaluationRunExecutionIntegrityError(
                "evaluation case execution target identity "
                "does not match run target"
            )

        if result.evidence.case_id != case.case_id:
            raise EvaluationRunExecutionIntegrityError(
                "evaluation case execution evidence identity "
                "does not match dataset case"
            )


def _mean(
    values: list[float],
) -> float:
    if not values:
        raise RuntimeError(
            "cannot aggregate empty evaluation metric values"
        )

    return sum(values) / len(values)


def _failure_reason(
    *,
    failed_case_count: int,
    incomplete_metrics: set[EvaluationMetric],
) -> str:
    parts: list[str] = []

    if failed_case_count:
        parts.append(
            f"{failed_case_count} evaluation case(s) "
            "reported provider errors"
        )

    if incomplete_metrics:
        names = ", ".join(
            sorted(
                metric.value
                for metric in incomplete_metrics
            )
        )
        parts.append(
            "incomplete metric evidence: "
            f"{names}"
        )

    if not parts:
        return "evaluation run did not produce complete metrics"

    return "; ".join(parts)
