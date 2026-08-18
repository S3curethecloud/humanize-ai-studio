from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from app.v2.domain.eval_execution import (
    EvaluationRunRequest,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_run_execution_service import (
    EvaluationRunExecutionService,
)
from app.v2.services.governed_eval_run_execution_service import (
    GovernedEvaluationRunExecutionService,
)


def _request() -> EvaluationRunRequest:
    return EvaluationRunRequest(
        run_id="governed-run",
        dataset=EvaluationDatasetIdentity(
            dataset_id="governed-suite",
            dataset_version="v1",
        ),
        target_id="deterministic-eval",
        metrics=(
            EvaluationMetric.PROVIDER_ERROR_RATE,
        ),
    )


def _run(
    *,
    outcome: EvaluationRunOutcome,
) -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id="governed-run",
            dataset=EvaluationDatasetIdentity(
                dataset_id="governed-suite",
                dataset_version="v1",
            ),
            target_id="deterministic-eval",
        ),
        outcome=outcome,
        evaluated_case_count=1,
        failed_case_count=(
            1
            if outcome is EvaluationRunOutcome.FAILED
            else 0
        ),
        metric_results=(
            (
                EvaluationMetricResult(
                    metric=(
                        EvaluationMetric.PROVIDER_ERROR_RATE
                    ),
                    value=0.0,
                ),
            )
            if outcome is EvaluationRunOutcome.SUCCEEDED
            else ()
        ),
        failure_reason=(
            "provider case failed"
            if outcome is EvaluationRunOutcome.FAILED
            else None
        ),
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        20,
        0,
        tzinfo=UTC,
    )


class StubRunExecution:
    def __init__(
        self,
        *,
        run: EvaluationRunRecord | None = None,
        error: Exception | None = None,
    ) -> None:
        self.run = run
        self.error = error
        self.calls = 0
        self.requests: list[
            EvaluationRunRequest
        ] = []

    def execute(
        self,
        request: EvaluationRunRequest,
    ) -> EvaluationRunRecord:
        self.calls += 1
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        if self.run is None:
            raise AssertionError(
                "stub run was not configured"
            )

        return self.run


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
    execution: StubRunExecution,
    repository: InMemoryEvaluationEvidenceRepository,
) -> GovernedEvaluationRunExecutionService:
    return GovernedEvaluationRunExecutionService(
        execution=cast(
            EvaluationRunExecutionService,
            execution,
        ),
        evidence=EvaluationEvidenceService(
            repository=repository,
        ),
    )


@pytest.mark.parametrize(
    "outcome",
    (
        EvaluationRunOutcome.SUCCEEDED,
        EvaluationRunOutcome.FAILED,
    ),
)
def test_terminal_run_is_recorded_before_return(
    outcome: EvaluationRunOutcome,
) -> None:
    run = _run(
        outcome=outcome,
    )
    execution = StubRunExecution(
        run=run,
    )
    repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        execution=execution,
        repository=repository,
    )

    result = service.execute(
        evidence_id="eval-run-evidence",
        request=_request(),
        observed_at=_observed_at(),
    )

    assert result is run
    assert execution.calls == 1
    assert execution.requests == [
        _request(),
    ]

    evidence = repository.get(
        "eval-run-evidence"
    )
    assert evidence is not None
    assert evidence.run == run
    assert evidence.gate_result is None
    assert evidence.observed_at == _observed_at()


def test_execution_exception_propagates_without_evidence() -> None:
    error = RuntimeError(
        "simulated run execution failure"
    )
    execution = StubRunExecution(
        error=error,
    )
    repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    service = _service(
        execution=execution,
        repository=repository,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated run execution failure",
    ) as caught:
        service.execute(
            evidence_id="missing-run-evidence",
            request=_request(),
            observed_at=_observed_at(),
        )

    assert caught.value is error
    assert execution.calls == 1
    assert (
        repository.get(
            "missing-run-evidence"
        )
        is None
    )


def test_evidence_failure_propagates_after_single_run_execution() -> None:
    run = _run(
        outcome=EvaluationRunOutcome.SUCCEEDED,
    )
    execution = StubRunExecution(
        run=run,
    )
    repository = (
        FailingEvaluationEvidenceRepository()
    )
    service = _service(
        execution=execution,
        repository=repository,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated evaluation evidence failure",
    ):
        service.execute(
            evidence_id="failed-evidence",
            request=_request(),
            observed_at=_observed_at(),
        )

    assert execution.calls == 1
