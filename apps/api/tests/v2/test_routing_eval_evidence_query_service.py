from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.domain.provider_routing import (
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceNotFoundError,
    EvaluationEvidenceQueryService,
    RoutingEvidenceNotFoundError,
    RoutingEvidenceQueryService,
)


def _observed_at(
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        8,
        17,
        12,
        minute,
        tzinfo=UTC,
    )


def _routing_record(
    *,
    evidence_id: str,
    policy_id: str = "policy-1",
    target_id: str = "target-a",
    observed_minute: int = 0,
) -> RoutingEvidenceRecord:
    policy = RoutingPolicy(
        policy_id=policy_id,
        ordered_target_ids=(target_id,),
    )

    decision = RoutingDecision(
        policy_id=policy_id,
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id=target_id,
        candidates=(
            RoutingCandidate(
                target_id=target_id,
                eligible=True,
            ),
        ),
    )

    return RoutingEvidenceRecord(
        evidence_id=evidence_id,
        policy=policy,
        decision=decision,
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ),
        observed_at=_observed_at(observed_minute),
    )


def _evaluation_record(
    *,
    evidence_id: str,
    run_id: str = "run-1",
    dataset_id: str = "dataset-1",
    dataset_version: str = "v1",
    target_id: str = "target-a",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
    observed_minute: int = 0,
) -> EvaluationEvidenceRecord:
    run = EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=run_id,
            dataset=EvaluationDatasetIdentity(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            ),
            target_id=target_id,
        ),
        outcome=outcome,
        evaluated_case_count=1,
        failed_case_count=(
            0
            if outcome is EvaluationRunOutcome.SUCCEEDED
            else 1
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
            None
            if outcome is EvaluationRunOutcome.SUCCEEDED
            else "evaluation failed"
        ),
    )

    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=run,
        observed_at=_observed_at(observed_minute),
    )


def test_routing_get_returns_exact_repository_record() -> None:
    repository = InMemoryRoutingEvidenceRepository()
    record = repository.create(
        _routing_record(
            evidence_id="routing-1",
        )
    )

    service = RoutingEvidenceQueryService(
        repository=repository,
    )

    assert (
        service.get(
            evidence_id="routing-1",
        )
        is record
    )


def test_routing_get_missing_raises_typed_error() -> None:
    service = RoutingEvidenceQueryService(
        repository=InMemoryRoutingEvidenceRepository(),
    )

    with pytest.raises(
        RoutingEvidenceNotFoundError,
        match="missing",
    ):
        service.get(
            evidence_id="missing",
        )


def test_routing_list_delegates_policy_filter() -> None:
    repository = InMemoryRoutingEvidenceRepository()

    expected = repository.create(
        _routing_record(
            evidence_id="routing-a",
            policy_id="policy-a",
        )
    )

    repository.create(
        _routing_record(
            evidence_id="routing-b",
            policy_id="policy-b",
        )
    )

    service = RoutingEvidenceQueryService(
        repository=repository,
    )

    assert service.list_records(
        policy_id="policy-a",
    ) == (expected,)


def test_routing_list_delegates_decision_filter() -> None:
    repository = InMemoryRoutingEvidenceRepository()

    expected = repository.create(
        _routing_record(
            evidence_id="routing-a",
        )
    )

    service = RoutingEvidenceQueryService(
        repository=repository,
    )

    assert service.list_records(
        decision_status=RoutingDecisionStatus.SELECTED,
    ) == (expected,)


def test_routing_list_delegates_execution_filter() -> None:
    repository = InMemoryRoutingEvidenceRepository()

    expected = repository.create(
        _routing_record(
            evidence_id="routing-a",
        )
    )

    service = RoutingEvidenceQueryService(
        repository=repository,
    )

    assert service.list_records(
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ),
    ) == (expected,)


def test_routing_list_preserves_repository_order_and_limit() -> None:
    repository = InMemoryRoutingEvidenceRepository()

    first = repository.create(
        _routing_record(
            evidence_id="routing-first",
            observed_minute=1,
        )
    )

    repository.create(
        _routing_record(
            evidence_id="routing-second",
            observed_minute=2,
        )
    )

    service = RoutingEvidenceQueryService(
        repository=repository,
    )

    assert service.list_records(
        limit=1,
    ) == (first,)


def test_routing_invalid_limit_remains_repository_authority() -> None:
    service = RoutingEvidenceQueryService(
        repository=InMemoryRoutingEvidenceRepository(),
    )

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        service.list_records(
            limit=0,
        )


def test_evaluation_get_returns_exact_repository_record() -> None:
    repository = InMemoryEvaluationEvidenceRepository()

    record = repository.create(
        _evaluation_record(
            evidence_id="evaluation-1",
        )
    )

    service = EvaluationEvidenceQueryService(
        repository=repository,
    )

    assert (
        service.get(
            evidence_id="evaluation-1",
        )
        is record
    )


def test_evaluation_get_missing_raises_typed_error() -> None:
    service = EvaluationEvidenceQueryService(
        repository=InMemoryEvaluationEvidenceRepository(),
    )

    with pytest.raises(
        EvaluationEvidenceNotFoundError,
        match="missing",
    ):
        service.get(
            evidence_id="missing",
        )


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        (
            {
                "run_id": "run-a",
            },
            "evaluation-a",
        ),
        (
            {
                "dataset_id": "dataset-a",
            },
            "evaluation-a",
        ),
        (
            {
                "dataset_version": "v2",
            },
            "evaluation-a",
        ),
        (
            {
                "target_id": "target-a",
            },
            "evaluation-a",
        ),
        (
            {
                "run_outcome": (
                    EvaluationRunOutcome.FAILED
                ),
            },
            "evaluation-a",
        ),
    ],
)
def test_evaluation_list_delegates_filters(
    query: dict[str, object],
    expected_id: str,
) -> None:
    repository = InMemoryEvaluationEvidenceRepository()

    expected = repository.create(
        _evaluation_record(
            evidence_id="evaluation-a",
            run_id="run-a",
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-a",
            outcome=EvaluationRunOutcome.FAILED,
        )
    )

    repository.create(
        _evaluation_record(
            evidence_id="evaluation-b",
            run_id="run-b",
            dataset_id="dataset-b",
            dataset_version="v1",
            target_id="target-b",
        )
    )

    service = EvaluationEvidenceQueryService(
        repository=repository,
    )

    result = service.list_records(
        **query,
    )

    assert result == (expected,)
    assert result[0].evidence_id == expected_id


def test_evaluation_list_preserves_repository_order_and_limit() -> None:
    repository = InMemoryEvaluationEvidenceRepository()

    first = repository.create(
        _evaluation_record(
            evidence_id="evaluation-first",
            observed_minute=1,
        )
    )

    repository.create(
        _evaluation_record(
            evidence_id="evaluation-second",
            observed_minute=2,
        )
    )

    service = EvaluationEvidenceQueryService(
        repository=repository,
    )

    assert service.list_records(
        limit=1,
    ) == (first,)


def test_evaluation_invalid_limit_remains_repository_authority() -> None:
    service = EvaluationEvidenceQueryService(
        repository=InMemoryEvaluationEvidenceRepository(),
    )

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        service.list_records(
            limit=10001,
        )
