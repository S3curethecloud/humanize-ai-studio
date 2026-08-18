from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

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
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
    InMemoryEvaluationRunRepository,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_quality_gate_service import (
    EvaluationQualityGateService,
)
from app.v2.services.governed_eval_quality_gate_service import (
    GovernedEvaluationGateIntegrityError,
    GovernedEvaluationGateRunResolutionError,
    GovernedEvaluationQualityGateService,
)


def _gate() -> EvaluationQualityGate:
    return EvaluationQualityGate(
        gate_id="governed-gate",
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
    )


def _run(
    *,
    value: float,
    run_id: str = "governed-run",
) -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=run_id,
            dataset=EvaluationDatasetIdentity(
                dataset_id="governed-suite",
                dataset_version="v1",
            ),
            target_id="deterministic-eval",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=1,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                value=value,
            ),
        ),
        failure_reason=None,
    )


def _result(
    *,
    decision: EvaluationGateDecision,
    run_id: str = "governed-run",
) -> EvaluationGateResult:
    value = (
        0.0
        if decision is EvaluationGateDecision.PASSED
        else 1.0
    )

    return EvaluationGateResult(
        gate=_gate(),
        run_id=run_id,
        decision=decision,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                value=value,
            ),
        ),
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        21,
        0,
        tzinfo=UTC,
    )


class StubQualityGate:
    def __init__(
        self,
        *,
        result: EvaluationGateResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.gates: list[
            EvaluationQualityGate
        ] = []
        self.run_ids: list[str] = []

    def evaluate(
        self,
        *,
        gate: EvaluationQualityGate,
        run_id: str,
    ) -> EvaluationGateResult:
        self.calls += 1
        self.gates.append(gate)
        self.run_ids.append(run_id)

        if self.error is not None:
            raise self.error

        if self.result is None:
            raise AssertionError(
                "stub gate result was not configured"
            )

        return self.result


class FailingRunRepository(
    InMemoryEvaluationRunRepository
):
    def get(
        self,
        run_id: str,
    ) -> EvaluationRunRecord | None:
        del run_id
        raise RuntimeError(
            "simulated run lookup failure"
        )


class FailingEvaluationEvidenceRepository(
    InMemoryEvaluationEvidenceRepository
):
    def create(self, record):
        del record
        raise RuntimeError(
            "simulated evaluation evidence failure"
        )


def _service(
    *,
    quality_gate: StubQualityGate,
    runs: EvaluationRunRepository,
    evidence_repository: (
        InMemoryEvaluationEvidenceRepository
    ),
) -> GovernedEvaluationQualityGateService:
    return GovernedEvaluationQualityGateService(
        quality_gate=cast(
            EvaluationQualityGateService,
            quality_gate,
        ),
        runs=runs,
        evidence=EvaluationEvidenceService(
            repository=evidence_repository,
        ),
    )


@pytest.mark.parametrize(
    "decision",
    (
        EvaluationGateDecision.PASSED,
        EvaluationGateDecision.FAILED,
    ),
)
def test_terminal_gate_result_is_recorded_before_return(
    decision: EvaluationGateDecision,
) -> None:
    value = (
        0.0
        if decision is EvaluationGateDecision.PASSED
        else 1.0
    )

    runs = InMemoryEvaluationRunRepository()
    run = _run(
        value=value,
    )
    runs.create(run)

    result = _result(
        decision=decision,
    )
    quality_gate = StubQualityGate(
        result=result,
    )
    evidence_repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        quality_gate=quality_gate,
        runs=runs,
        evidence_repository=evidence_repository,
    )

    returned = service.evaluate(
        evidence_id="eval-gate-evidence",
        gate=_gate(),
        run_id="governed-run",
        observed_at=_observed_at(),
    )

    assert returned is result
    assert quality_gate.calls == 1
    assert quality_gate.gates == [
        _gate(),
    ]
    assert quality_gate.run_ids == [
        "governed-run",
    ]

    evidence = evidence_repository.get(
        "eval-gate-evidence"
    )
    assert evidence is not None
    assert evidence.run == run
    assert evidence.gate_result == result
    assert evidence.observed_at == _observed_at()


def test_gate_exception_propagates_without_evidence() -> None:
    error = RuntimeError(
        "simulated gate evaluation failure"
    )
    quality_gate = StubQualityGate(
        error=error,
    )
    runs = InMemoryEvaluationRunRepository()
    runs.create(
        _run(
            value=0.0,
        )
    )
    evidence_repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        quality_gate=quality_gate,
        runs=runs,
        evidence_repository=evidence_repository,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated gate evaluation failure",
    ) as caught:
        service.evaluate(
            evidence_id="missing-gate-evidence",
            gate=_gate(),
            run_id="governed-run",
            observed_at=_observed_at(),
        )

    assert caught.value is error
    assert quality_gate.calls == 1
    assert (
        evidence_repository.get(
            "missing-gate-evidence"
        )
        is None
    )


def test_gate_result_run_identity_mismatch_fails_closed() -> None:
    runs = InMemoryEvaluationRunRepository()
    runs.create(
        _run(
            value=0.0,
        )
    )
    quality_gate = StubQualityGate(
        result=_result(
            decision=EvaluationGateDecision.PASSED,
            run_id="different-run",
        ),
    )
    evidence_repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        quality_gate=quality_gate,
        runs=runs,
        evidence_repository=evidence_repository,
    )

    with pytest.raises(
        GovernedEvaluationGateIntegrityError,
        match="does not match requested run",
    ):
        service.evaluate(
            evidence_id="identity-mismatch",
            gate=_gate(),
            run_id="governed-run",
            observed_at=_observed_at(),
        )

    assert quality_gate.calls == 1
    assert (
        evidence_repository.get(
            "identity-mismatch"
        )
        is None
    )


def test_missing_run_after_gate_result_fails_closed() -> None:
    quality_gate = StubQualityGate(
        result=_result(
            decision=EvaluationGateDecision.PASSED,
        ),
    )
    evidence_repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        quality_gate=quality_gate,
        runs=InMemoryEvaluationRunRepository(),
        evidence_repository=evidence_repository,
    )

    with pytest.raises(
        GovernedEvaluationGateRunResolutionError,
        match="run does not exist",
    ):
        service.evaluate(
            evidence_id="missing-run",
            gate=_gate(),
            run_id="governed-run",
            observed_at=_observed_at(),
        )

    assert quality_gate.calls == 1
    assert (
        evidence_repository.get(
            "missing-run"
        )
        is None
    )


def test_run_lookup_failure_is_wrapped_without_evidence() -> None:
    quality_gate = StubQualityGate(
        result=_result(
            decision=EvaluationGateDecision.PASSED,
        ),
    )
    evidence_repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        quality_gate=quality_gate,
        runs=FailingRunRepository(),
        evidence_repository=evidence_repository,
    )

    with pytest.raises(
        GovernedEvaluationGateRunResolutionError,
        match="run lookup failed",
    ):
        service.evaluate(
            evidence_id="lookup-failure",
            gate=_gate(),
            run_id="governed-run",
            observed_at=_observed_at(),
        )

    assert quality_gate.calls == 1
    assert (
        evidence_repository.get(
            "lookup-failure"
        )
        is None
    )


def test_evidence_failure_propagates_after_single_gate_evaluation() -> None:
    runs = InMemoryEvaluationRunRepository()
    runs.create(
        _run(
            value=0.0,
        )
    )
    quality_gate = StubQualityGate(
        result=_result(
            decision=EvaluationGateDecision.PASSED,
        ),
    )
    service = _service(
        quality_gate=quality_gate,
        runs=runs,
        evidence_repository=(
            FailingEvaluationEvidenceRepository()
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="simulated evaluation evidence failure",
    ):
        service.evaluate(
            evidence_id="failed-gate-evidence",
            gate=_gate(),
            run_id="governed-run",
            observed_at=_observed_at(),
        )

    assert quality_gate.calls == 1
