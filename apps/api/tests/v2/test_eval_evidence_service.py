from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationDatasetIdentity,
    EvaluationGateDecision,
    EvaluationGateResult,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationQualityGate,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
    EvaluationThreshold,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)


def _run(
    *,
    run_id: str = "run-1",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
    metric_value: float = 0.0,
) -> EvaluationRunRecord:
    identity = EvaluationRunIdentity(
        run_id=run_id,
        dataset=EvaluationDatasetIdentity(
            dataset_id="dataset-1",
            dataset_version="v1",
        ),
        target_id="target-a",
    )

    if outcome is EvaluationRunOutcome.FAILED:
        return EvaluationRunRecord(
            identity=identity,
            outcome=outcome,
            evaluated_case_count=2,
            failed_case_count=1,
            metric_results=(
                EvaluationMetricResult(
                    metric=(
                        EvaluationMetric.PROVIDER_ERROR_RATE
                    ),
                    value=metric_value,
                ),
            ),
            failure_reason="provider error",
        )

    return EvaluationRunRecord(
        identity=identity,
        outcome=outcome,
        evaluated_case_count=2,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                value=metric_value,
            ),
        ),
    )


def _gate_result(
    *,
    run_id: str = "run-1",
    metric_value: float = 0.0,
    decision: EvaluationGateDecision = (
        EvaluationGateDecision.PASSED
    ),
) -> EvaluationGateResult:
    return EvaluationGateResult(
        gate=EvaluationQualityGate(
            gate_id="gate-1",
            thresholds=(
                EvaluationThreshold(
                    metric=(
                        EvaluationMetric.PROVIDER_ERROR_RATE
                    ),
                    comparator=(
                        EvaluationComparator.AT_MOST
                    ),
                    threshold=0.0,
                ),
            ),
        ),
        run_id=run_id,
        decision=decision,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                value=metric_value,
            ),
        ),
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )


def _service(
) -> tuple[
    EvaluationEvidenceService,
    InMemoryEvaluationEvidenceRepository,
]:
    repository = InMemoryEvaluationEvidenceRepository()

    return (
        EvaluationEvidenceService(
            repository=repository,
        ),
        repository,
    )


def test_records_successful_run_without_gate() -> None:
    service, repository = _service()
    run = _run()

    record = service.record_run(
        evidence_id="evidence-run",
        run=run,
        observed_at=_observed_at(),
    )

    assert record.run == run
    assert record.gate_result is None
    assert (
        repository.get("evidence-run")
        == record
    )


def test_records_failed_run_without_gate() -> None:
    service, repository = _service()

    run = _run(
        outcome=EvaluationRunOutcome.FAILED,
        metric_value=0.5,
    )

    record = service.record_run(
        evidence_id="evidence-failed-run",
        run=run,
        observed_at=_observed_at(),
    )

    assert (
        record.run.outcome
        is EvaluationRunOutcome.FAILED
    )
    assert record.gate_result is None
    assert (
        repository.get("evidence-failed-run")
        == record
    )


def test_records_successful_run_with_gate() -> None:
    service, repository = _service()

    run = _run()
    gate_result = _gate_result()

    record = service.record_gate(
        evidence_id="evidence-gate",
        run=run,
        gate_result=gate_result,
        observed_at=_observed_at(),
    )

    assert record.run == run
    assert record.gate_result == gate_result
    assert (
        repository.get("evidence-gate")
        == record
    )


def test_records_failed_quality_gate_result() -> None:
    service, _ = _service()

    run = _run(
        metric_value=0.25,
    )

    gate_result = _gate_result(
        metric_value=0.25,
        decision=EvaluationGateDecision.FAILED,
    )

    record = service.record_gate(
        evidence_id="evidence-gate-failed",
        run=run,
        gate_result=gate_result,
        observed_at=_observed_at(),
    )

    assert (
        record.gate_result is not None
    )
    assert (
        record.gate_result.decision
        is EvaluationGateDecision.FAILED
    )


def test_observed_timestamp_is_caller_supplied() -> None:
    service, _ = _service()

    observed_at = datetime(
        2026,
        8,
        17,
        8,
        15,
        tzinfo=UTC,
    )

    record = service.record_run(
        evidence_id="evidence-time",
        run=_run(),
        observed_at=observed_at,
    )

    assert record.observed_at == observed_at


def test_duplicate_evidence_id_is_not_suppressed() -> None:
    service, repository = _service()
    run = _run()

    first = service.record_run(
        evidence_id="duplicate",
        run=run,
        observed_at=_observed_at(),
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        service.record_run(
            evidence_id="duplicate",
            run=run,
            observed_at=_observed_at(),
        )

    assert repository.get("duplicate") == first


def test_gate_run_identity_mismatch_fails_before_persistence() -> None:
    service, repository = _service()

    with pytest.raises(
        ValueError,
        match="run identity",
    ):
        service.record_gate(
            evidence_id="identity-mismatch",
            run=_run(
                run_id="run-1",
            ),
            gate_result=_gate_result(
                run_id="run-other",
            ),
            observed_at=_observed_at(),
        )

    assert repository.get(
        "identity-mismatch"
    ) is None


def test_gate_metric_value_mismatch_fails_before_persistence() -> None:
    service, repository = _service()

    with pytest.raises(
        ValueError,
        match="metric value",
    ):
        service.record_gate(
            evidence_id="metric-mismatch",
            run=_run(
                metric_value=0.0,
            ),
            gate_result=_gate_result(
                metric_value=0.5,
                decision=EvaluationGateDecision.FAILED,
            ),
            observed_at=_observed_at(),
        )

    assert repository.get(
        "metric-mismatch"
    ) is None


def test_gate_cannot_be_recorded_for_failed_run() -> None:
    service, repository = _service()

    with pytest.raises(
        ValueError,
        match="successful evaluation run",
    ):
        service.record_gate(
            evidence_id="failed-run-gate",
            run=_run(
                outcome=EvaluationRunOutcome.FAILED,
                metric_value=0.5,
            ),
            gate_result=_gate_result(
                metric_value=0.5,
                decision=EvaluationGateDecision.FAILED,
            ),
            observed_at=_observed_at(),
        )

    assert repository.get(
        "failed-run-gate"
    ) is None


def test_naive_timestamp_is_rejected_before_persistence() -> None:
    service, repository = _service()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        service.record_run(
            evidence_id="naive-time",
            run=_run(),
            observed_at=datetime(
                2026,
                8,
                17,
                12,
                0,
            ),
        )

    assert repository.get("naive-time") is None
