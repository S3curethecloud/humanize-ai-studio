from __future__ import annotations

import pytest

from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationDatasetIdentity,
    EvaluationGateDecision,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationQualityGate,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
    EvaluationThreshold,
)
from app.v2.repositories.eval_run import (
    InMemoryEvaluationRunRepository,
)
from app.v2.services.eval_quality_gate_service import (
    EvaluationGateRunNotComparableError,
    EvaluationGateRunResolutionError,
    EvaluationQualityGateService,
)


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="quality-suite",
        dataset_version="v1",
    )


def _run(
    *,
    run_id: str = "run-001",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
    metrics: tuple[
        EvaluationMetricResult,
        ...,
    ] = (
        EvaluationMetricResult(
            metric=EvaluationMetric.CLAIM_PRESERVATION,
            value=0.95,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.NATURALNESS,
            value=0.90,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.REWRITE_DISTANCE,
            value=0.35,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.LATENCY_MS,
            value=250.0,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.PROVIDER_ERROR_RATE,
            value=0.0,
        ),
    ),
) -> EvaluationRunRecord:
    identity = EvaluationRunIdentity(
        run_id=run_id,
        dataset=_dataset_identity(),
        target_id="openai-primary",
    )

    if outcome is EvaluationRunOutcome.FAILED:
        return EvaluationRunRecord(
            identity=identity,
            outcome=outcome,
            evaluated_case_count=10,
            failed_case_count=1,
            metric_results=metrics,
            failure_reason="evaluation evidence incomplete",
        )

    return EvaluationRunRecord(
        identity=identity,
        outcome=outcome,
        evaluated_case_count=10,
        failed_case_count=0,
        metric_results=metrics,
    )


def _gate(
    *,
    gate_id: str = "production-quality",
    thresholds: tuple[
        EvaluationThreshold,
        ...,
    ] = (
        EvaluationThreshold(
            metric=EvaluationMetric.CLAIM_PRESERVATION,
            comparator=EvaluationComparator.AT_LEAST,
            threshold=0.90,
        ),
        EvaluationThreshold(
            metric=EvaluationMetric.NATURALNESS,
            comparator=EvaluationComparator.AT_LEAST,
            threshold=0.85,
        ),
        EvaluationThreshold(
            metric=EvaluationMetric.LATENCY_MS,
            comparator=EvaluationComparator.AT_MOST,
            threshold=500.0,
        ),
        EvaluationThreshold(
            metric=EvaluationMetric.PROVIDER_ERROR_RATE,
            comparator=EvaluationComparator.AT_MOST,
            threshold=0.01,
        ),
    ),
) -> EvaluationQualityGate:
    return EvaluationQualityGate(
        gate_id=gate_id,
        thresholds=thresholds,
    )


def _service_with_run(
    run: EvaluationRunRecord | None = None,
):
    runs = InMemoryEvaluationRunRepository()

    if run is not None:
        runs.create(run)

    service = EvaluationQualityGateService(
        runs=runs
    )

    return service, runs


def test_passing_run_produces_passed_gate() -> None:
    run = _run()
    service, _ = _service_with_run(run)

    result = service.evaluate(
        gate=_gate(),
        run_id=run.identity.run_id,
    )

    assert (
        result.decision
        is EvaluationGateDecision.PASSED
    )


def test_failing_at_least_threshold_fails_gate() -> None:
    run = _run(
        metrics=(
            EvaluationMetricResult(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                value=0.80,
            ),
            EvaluationMetricResult(
                metric=EvaluationMetric.NATURALNESS,
                value=0.90,
            ),
        )
    )
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.90,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.NATURALNESS,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.85,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert (
        result.decision
        is EvaluationGateDecision.FAILED
    )


def test_failing_at_most_threshold_fails_gate() -> None:
    run = _run(
        metrics=(
            EvaluationMetricResult(
                metric=EvaluationMetric.LATENCY_MS,
                value=750.0,
            ),
        )
    )
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=EvaluationComparator.AT_MOST,
                threshold=500.0,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert (
        result.decision
        is EvaluationGateDecision.FAILED
    )


@pytest.mark.parametrize(
    (
        "comparator",
        "value",
        "threshold",
    ),
    [
        (
            EvaluationComparator.AT_LEAST,
            0.90,
            0.90,
        ),
        (
            EvaluationComparator.AT_MOST,
            500.0,
            500.0,
        ),
    ],
)
def test_threshold_boundaries_are_inclusive(
    comparator: EvaluationComparator,
    value: float,
    threshold: float,
) -> None:
    run = _run(
        metrics=(
            EvaluationMetricResult(
                metric=EvaluationMetric.LATENCY_MS,
                value=value,
            ),
        )
    )
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=comparator,
                threshold=threshold,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert (
        result.decision
        is EvaluationGateDecision.PASSED
    )


def test_result_preserves_gate_and_run_identity() -> None:
    run = _run(
        run_id="run-specific"
    )
    gate = _gate(
        gate_id="gate-specific"
    )
    service, _ = _service_with_run(run)

    result = service.evaluate(
        gate=gate,
        run_id="run-specific",
    )

    assert result.run_id == "run-specific"
    assert result.gate == gate
    assert result.gate.gate_id == "gate-specific"


def test_result_metrics_exactly_match_gate_metrics() -> None:
    run = _run()
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.NATURALNESS,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.85,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.90,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert tuple(
        metric.metric
        for metric in result.metric_results
    ) == (
        EvaluationMetric.NATURALNESS,
        EvaluationMetric.CLAIM_PRESERVATION,
    )


def test_result_metric_order_follows_gate_threshold_order() -> None:
    run = _run()
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=EvaluationComparator.AT_MOST,
                threshold=500.0,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.NATURALNESS,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.85,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.90,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert tuple(
        metric.metric
        for metric in result.metric_results
    ) == (
        EvaluationMetric.LATENCY_MS,
        EvaluationMetric.NATURALNESS,
        EvaluationMetric.CLAIM_PRESERVATION,
    )


def test_extra_run_metrics_are_not_copied_into_result() -> None:
    run = _run()
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.NATURALNESS,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.85,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert len(
        result.metric_results
    ) == 1
    assert (
        result.metric_results[0].metric
        is EvaluationMetric.NATURALNESS
    )


def test_missing_gate_metric_fails_closed() -> None:
    run = _run(
        metrics=(
            EvaluationMetricResult(
                metric=EvaluationMetric.NATURALNESS,
                value=0.90,
            ),
        )
    )
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.90,
            ),
        )
    )

    with pytest.raises(
        EvaluationGateRunNotComparableError,
        match="required gate metric",
    ):
        service.evaluate(
            gate=gate,
            run_id=run.identity.run_id,
        )


def test_failed_run_is_not_gate_comparable() -> None:
    run = _run(
        outcome=EvaluationRunOutcome.FAILED
    )
    service, _ = _service_with_run(run)

    with pytest.raises(
        EvaluationGateRunNotComparableError,
        match="successful evaluation run",
    ):
        service.evaluate(
            gate=_gate(),
            run_id=run.identity.run_id,
        )


def test_missing_run_fails_closed() -> None:
    service, _ = _service_with_run()

    with pytest.raises(
        EvaluationGateRunResolutionError,
        match="does not exist",
    ):
        service.evaluate(
            gate=_gate(),
            run_id="missing-run",
        )


class BrokenRunRepository:
    def create(
        self,
        record: EvaluationRunRecord,
    ) -> EvaluationRunRecord:
        return record

    def get(
        self,
        run_id: str,
    ) -> EvaluationRunRecord | None:
        raise RuntimeError(
            "storage unavailable"
        )

    def list_runs(
        self,
        *,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationRunRecord, ...]:
        return ()


def test_repository_failure_fails_closed() -> None:
    service = EvaluationQualityGateService(
        runs=BrokenRunRepository()
    )

    with pytest.raises(
        EvaluationGateRunResolutionError,
        match="lookup failed",
    ):
        service.evaluate(
            gate=_gate(),
            run_id="run-001",
        )


class WrongIdentityRunRepository:
    def __init__(
        self,
        record: EvaluationRunRecord,
    ) -> None:
        self._record = record

    def create(
        self,
        record: EvaluationRunRecord,
    ) -> EvaluationRunRecord:
        return record

    def get(
        self,
        run_id: str,
    ) -> EvaluationRunRecord | None:
        return self._record

    def list_runs(
        self,
        *,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationRunRecord, ...]:
        return (self._record,)


def test_repository_identity_mismatch_fails_closed() -> None:
    service = EvaluationQualityGateService(
        runs=WrongIdentityRunRepository(
            _run(
                run_id="different-run"
            )
        )
    )

    with pytest.raises(
        EvaluationGateRunResolutionError,
        match="different run identity",
    ):
        service.evaluate(
            gate=_gate(),
            run_id="requested-run",
        )


def test_gate_evaluation_does_not_mutate_run() -> None:
    run = _run()
    before = run.model_dump()

    service, runs = _service_with_run(run)

    service.evaluate(
        gate=_gate(),
        run_id=run.identity.run_id,
    )

    assert run.model_dump() == before
    assert (
        runs.get(run.identity.run_id)
        == run
    )


def test_gate_evaluation_does_not_create_new_run() -> None:
    run = _run()
    service, runs = _service_with_run(run)

    before = runs.list_runs()

    service.evaluate(
        gate=_gate(),
        run_id=run.identity.run_id,
    )

    assert runs.list_runs() == before


def test_single_failed_threshold_fails_entire_gate() -> None:
    run = _run(
        metrics=(
            EvaluationMetricResult(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                value=0.95,
            ),
            EvaluationMetricResult(
                metric=EvaluationMetric.NATURALNESS,
                value=0.70,
            ),
            EvaluationMetricResult(
                metric=EvaluationMetric.LATENCY_MS,
                value=200.0,
            ),
        )
    )
    service, _ = _service_with_run(run)

    gate = _gate(
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.90,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.NATURALNESS,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.85,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=EvaluationComparator.AT_MOST,
                threshold=500.0,
            ),
        )
    )

    result = service.evaluate(
        gate=gate,
        run_id=run.identity.run_id,
    )

    assert (
        result.decision
        is EvaluationGateDecision.FAILED
    )


def test_all_thresholds_must_pass() -> None:
    run = _run()
    service, _ = _service_with_run(run)

    result = service.evaluate(
        gate=_gate(),
        run_id=run.identity.run_id,
    )

    assert all(
        (
            result_by_metric.value
            >= threshold.threshold
            if (
                threshold.comparator
                is EvaluationComparator.AT_LEAST
            )
            else result_by_metric.value
            <= threshold.threshold
        )
        for threshold in result.gate.thresholds
        for result_by_metric in result.metric_results
        if (
            result_by_metric.metric
            is threshold.metric
        )
    )
