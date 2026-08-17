from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationCaseReference,
    EvaluationDataset,
    EvaluationDatasetCase,
    EvaluationReferenceKind,
)
from app.v2.domain.eval_execution import (
    EvaluationCaseExecutionResult,
    EvaluationRunRequest,
)
from app.v2.domain.eval_metrics import (
    EvaluationCaseExecutionEvidence,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationRunOutcome,
)
from app.v2.repositories.eval_dataset import (
    InMemoryEvaluationDatasetRepository,
)
from app.v2.repositories.eval_run import (
    InMemoryEvaluationRunRepository,
)
from app.v2.services.eval_metric_service import (
    DeterministicEvaluationMetricService,
)
from app.v2.services.eval_run_execution_service import (
    EvaluationRunDatasetResolutionError,
    EvaluationRunExecutionIntegrityError,
    EvaluationRunExecutionService,
)


def _identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="quality-suite",
        dataset_version="v1",
    )


def _case(
    *,
    case_id: str,
    text: str,
) -> EvaluationDatasetCase:
    return EvaluationDatasetCase(
        case_id=case_id,
        input=EvaluationCaseInput(
            text=text
        ),
        references=(
            EvaluationCaseReference(
                reference_id=f"{case_id}-claim",
                kind=(
                    EvaluationReferenceKind.REQUIRED_CLAIM
                ),
                value="May 3",
            ),
        ),
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=_identity(),
        cases=(
            _case(
                case_id="case-1",
                text="Launch date: May 3.",
            ),
            _case(
                case_id="case-2",
                text="The event happens May 3.",
            ),
        ),
    )


def _request(
    *,
    run_id: str = "run-001",
    target_id: str = "openai-primary",
    metrics: tuple[
        EvaluationMetric,
        ...,
    ] = (
        EvaluationMetric.CLAIM_PRESERVATION,
        EvaluationMetric.REWRITE_DISTANCE,
        EvaluationMetric.LATENCY_MS,
        EvaluationMetric.PROVIDER_ERROR_RATE,
    ),
) -> EvaluationRunRequest:
    return EvaluationRunRequest(
        run_id=run_id,
        dataset=_identity(),
        target_id=target_id,
        metrics=metrics,
    )


@dataclass
class StubCaseExecutor:
    results: dict[
        str,
        EvaluationCaseExecutionResult,
    ]
    calls: list[
        tuple[str, str]
    ] = field(
        default_factory=list
    )

    def execute(
        self,
        *,
        case: EvaluationDatasetCase,
        target_id: str,
    ) -> EvaluationCaseExecutionResult:
        self.calls.append(
            (
                case.case_id,
                target_id,
            )
        )
        return self.results[
            case.case_id
        ]


def _result(
    *,
    case_id: str,
    target_id: str = "openai-primary",
    output_text: str | None = None,
    latency_ms: float | None = 100.0,
    provider_error: bool = False,
    provider_error_category: str | None = None,
    naturalness_score: float | None = 0.9,
) -> EvaluationCaseExecutionResult:
    return EvaluationCaseExecutionResult(
        target_id=target_id,
        evidence=EvaluationCaseExecutionEvidence(
            case_id=case_id,
            output_text=output_text,
            latency_ms=latency_ms,
            provider_error=provider_error,
            provider_error_category=(
                provider_error_category
            ),
            naturalness_score=naturalness_score,
        ),
    )


def _executor(
    *,
    first: EvaluationCaseExecutionResult | None = None,
    second: EvaluationCaseExecutionResult | None = None,
) -> StubCaseExecutor:
    return StubCaseExecutor(
        results={
            "case-1": (
                first
                or _result(
                    case_id="case-1",
                    output_text=(
                        "Launch date: May 3."
                    ),
                    latency_ms=100.0,
                )
            ),
            "case-2": (
                second
                or _result(
                    case_id="case-2",
                    output_text=(
                        "The event happens May 3."
                    ),
                    latency_ms=200.0,
                )
            ),
        }
    )


def _service(
    *,
    executor: StubCaseExecutor | None = None,
):
    datasets = InMemoryEvaluationDatasetRepository()
    datasets.create(_dataset())

    runs = InMemoryEvaluationRunRepository()

    service = EvaluationRunExecutionService(
        datasets=datasets,
        runs=runs,
        case_executor=executor or _executor(),
        metrics=DeterministicEvaluationMetricService(),
    )

    return service, runs


def test_run_executes_every_dataset_case_in_order() -> None:
    executor = _executor()
    service, _ = _service(
        executor=executor
    )

    service.execute(_request())

    assert executor.calls == [
        (
            "case-1",
            "openai-primary",
        ),
        (
            "case-2",
            "openai-primary",
        ),
    ]


def test_successful_run_preserves_identity() -> None:
    executor = _executor(
        first=_result(
            case_id="case-1",
            target_id="target-specific",
            output_text="Launch date: May 3.",
        ),
        second=_result(
            case_id="case-2",
            target_id="target-specific",
            output_text="The event happens May 3.",
        ),
    )
    service, _ = _service(
        executor=executor
    )

    record = service.execute(
        _request(
            run_id="run-specific",
            target_id="target-specific",
        )
    )

    assert record.identity.run_id == "run-specific"
    assert record.identity.dataset == _identity()
    assert (
        record.identity.target_id
        == "target-specific"
    )


def test_successful_run_counts_all_cases() -> None:
    service, _ = _service()

    record = service.execute(
        _request()
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.SUCCEEDED
    )
    assert record.evaluated_case_count == 2
    assert record.failed_case_count == 0


def test_successful_run_aggregates_metrics() -> None:
    service, _ = _service()

    record = service.execute(
        _request()
    )

    values = {
        result.metric: result.value
        for result in record.metric_results
    }

    assert values[
        EvaluationMetric.CLAIM_PRESERVATION
    ] == 1.0
    assert values[
        EvaluationMetric.REWRITE_DISTANCE
    ] == 0.0
    assert values[
        EvaluationMetric.LATENCY_MS
    ] == 150.0
    assert values[
        EvaluationMetric.PROVIDER_ERROR_RATE
    ] == 0.0


def test_metric_result_order_matches_request_order() -> None:
    service, _ = _service()

    metrics = (
        EvaluationMetric.LATENCY_MS,
        EvaluationMetric.CLAIM_PRESERVATION,
        EvaluationMetric.PROVIDER_ERROR_RATE,
    )

    record = service.execute(
        _request(
            metrics=metrics
        )
    )

    assert tuple(
        result.metric
        for result in record.metric_results
    ) == metrics


def test_naturalness_is_aggregated_from_explicit_evidence() -> None:
    executor = _executor(
        first=_result(
            case_id="case-1",
            output_text="Launch date: May 3.",
            naturalness_score=0.8,
        ),
        second=_result(
            case_id="case-2",
            output_text="The event happens May 3.",
            naturalness_score=1.0,
        ),
    )
    service, _ = _service(
        executor=executor
    )

    record = service.execute(
        _request(
            metrics=(
                EvaluationMetric.NATURALNESS,
            )
        )
    )

    assert record.metric_results[0].value == 0.9


def test_provider_error_marks_run_failed() -> None:
    executor = _executor(
        second=_result(
            case_id="case-2",
            output_text=None,
            provider_error=True,
            provider_error_category="transport",
        )
    )
    service, _ = _service(
        executor=executor
    )

    record = service.execute(
        _request(
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            )
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.FAILED
    )
    assert record.evaluated_case_count == 2
    assert record.failed_case_count == 1
    assert record.metric_results[0].value == 0.5
    assert record.failure_reason is not None
    assert "provider errors" in record.failure_reason


def test_provider_error_does_not_fabricate_output_metric() -> None:
    executor = _executor(
        second=_result(
            case_id="case-2",
            output_text=None,
            provider_error=True,
            provider_error_category="transport",
        )
    )
    service, _ = _service(
        executor=executor
    )

    record = service.execute(
        _request(
            metrics=(
                EvaluationMetric.CLAIM_PRESERVATION,
                EvaluationMetric.PROVIDER_ERROR_RATE,
            )
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.FAILED
    )

    assert tuple(
        result.metric
        for result in record.metric_results
    ) == (
        EvaluationMetric.PROVIDER_ERROR_RATE,
    )

    assert record.failure_reason is not None
    assert "claim_preservation" in record.failure_reason


def test_missing_metric_evidence_marks_run_failed() -> None:
    executor = _executor(
        second=_result(
            case_id="case-2",
            output_text="The event happens May 3.",
            latency_ms=None,
        )
    )
    service, _ = _service(
        executor=executor
    )

    record = service.execute(
        _request(
            metrics=(
                EvaluationMetric.LATENCY_MS,
            )
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.FAILED
    )
    assert record.failed_case_count == 0
    assert record.metric_results == ()
    assert record.failure_reason is not None
    assert "latency_ms" in record.failure_reason


def test_run_record_is_persisted_once() -> None:
    service, runs = _service()

    record = service.execute(
        _request(
            run_id="persisted-run"
        )
    )

    assert (
        runs.get("persisted-run")
        == record
    )
    assert len(
        runs.list_runs()
    ) == 1


def test_duplicate_run_id_is_rejected_by_repository() -> None:
    service, _ = _service()

    service.execute(
        _request(
            run_id="duplicate-run"
        )
    )

    with pytest.raises(
        ValueError,
        match="evaluation run already exists",
    ):
        service.execute(
            _request(
                run_id="duplicate-run"
            )
        )


def test_missing_dataset_fails_before_case_execution() -> None:
    datasets = InMemoryEvaluationDatasetRepository()
    runs = InMemoryEvaluationRunRepository()
    executor = _executor()

    service = EvaluationRunExecutionService(
        datasets=datasets,
        runs=runs,
        case_executor=executor,
        metrics=DeterministicEvaluationMetricService(),
    )

    with pytest.raises(
        EvaluationRunDatasetResolutionError,
        match="does not exist",
    ):
        service.execute(
            _request()
        )

    assert executor.calls == []
    assert runs.list_runs() == ()


class BrokenDatasetRepository:
    def create(self, dataset):
        return dataset

    def get(self, identity):
        raise RuntimeError("storage unavailable")

    def list_datasets(
        self,
        *,
        dataset_id=None,
        limit=1000,
    ):
        return ()


def test_dataset_repository_failure_fails_closed() -> None:
    runs = InMemoryEvaluationRunRepository()
    executor = _executor()

    service = EvaluationRunExecutionService(
        datasets=BrokenDatasetRepository(),
        runs=runs,
        case_executor=executor,
        metrics=DeterministicEvaluationMetricService(),
    )

    with pytest.raises(
        EvaluationRunDatasetResolutionError,
        match="lookup failed",
    ):
        service.execute(
            _request()
        )

    assert executor.calls == []
    assert runs.list_runs() == ()


def test_executor_target_identity_mismatch_fails_closed() -> None:
    executor = _executor(
        first=_result(
            case_id="case-1",
            target_id="different-target",
            output_text="Launch date: May 3.",
        )
    )
    service, runs = _service(
        executor=executor
    )

    with pytest.raises(
        EvaluationRunExecutionIntegrityError,
        match="target identity",
    ):
        service.execute(
            _request()
        )

    assert runs.list_runs() == ()


def test_executor_case_identity_mismatch_fails_closed() -> None:
    executor = _executor(
        first=_result(
            case_id="wrong-case",
            output_text="Launch date: May 3.",
        )
    )
    service, runs = _service(
        executor=executor
    )

    with pytest.raises(
        EvaluationRunExecutionIntegrityError,
        match="evidence identity",
    ):
        service.execute(
            _request()
        )

    assert runs.list_runs() == ()


class ExplodingExecutor:
    def execute(
        self,
        *,
        case: EvaluationDatasetCase,
        target_id: str,
    ) -> EvaluationCaseExecutionResult:
        raise RuntimeError(
            "unexpected execution failure"
        )


def test_unexpected_executor_failure_propagates_without_record() -> None:
    datasets = InMemoryEvaluationDatasetRepository()
    datasets.create(_dataset())
    runs = InMemoryEvaluationRunRepository()

    service = EvaluationRunExecutionService(
        datasets=datasets,
        runs=runs,
        case_executor=ExplodingExecutor(),
        metrics=DeterministicEvaluationMetricService(),
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected execution failure",
    ):
        service.execute(
            _request()
        )

    assert runs.list_runs() == ()


def test_request_rejects_duplicate_metrics() -> None:
    with pytest.raises(
        ValueError,
        match="metrics must be unique",
    ):
        _request(
            metrics=(
                EvaluationMetric.LATENCY_MS,
                EvaluationMetric.LATENCY_MS,
            )
        )


def test_request_requires_at_least_one_metric() -> None:
    with pytest.raises(ValueError):
        _request(
            metrics=()
        )


def test_case_executor_cannot_change_authorized_target_between_cases() -> None:
    executor = _executor(
        second=_result(
            case_id="case-2",
            target_id="unauthorized-target",
            output_text="The event happens May 3.",
        )
    )
    service, runs = _service(
        executor=executor
    )

    with pytest.raises(
        EvaluationRunExecutionIntegrityError,
        match="target identity",
    ):
        service.execute(
            _request()
        )

    assert runs.list_runs() == ()


def test_partial_metrics_are_not_averaged_over_fewer_cases() -> None:
    executor = _executor(
        second=_result(
            case_id="case-2",
            output_text="The event happens May 3.",
            naturalness_score=None,
        )
    )
    service, _ = _service(
        executor=executor
    )

    record = service.execute(
        _request(
            metrics=(
                EvaluationMetric.NATURALNESS,
                EvaluationMetric.PROVIDER_ERROR_RATE,
            )
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.FAILED
    )
    assert tuple(
        result.metric
        for result in record.metric_results
    ) == (
        EvaluationMetric.PROVIDER_ERROR_RATE,
    )


def test_all_requested_metrics_are_required_for_success() -> None:
    service, _ = _service()

    record = service.execute(
        _request(
            metrics=(
                EvaluationMetric.LATENCY_MS,
                EvaluationMetric.PROVIDER_ERROR_RATE,
            )
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.SUCCEEDED
    )
    assert len(record.metric_results) == 2
    assert record.failure_reason is None
