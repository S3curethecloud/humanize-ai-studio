from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

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
from app.v2.domain.provider_routing import (
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceAttemptOutcome,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
    RoutingExecutionAttemptEvidence,
)
from app.v2.repositories.routing_eval_evidence import (
    EvaluationEvidenceRepository,
    InMemoryEvaluationEvidenceRepository,
    InMemoryRoutingEvidenceRepository,
    RoutingEvidenceRepository,
    SQLiteEvaluationEvidenceRepository,
    SQLiteRoutingEvidenceRepository,
)


def _routing_policy(
    *,
    policy_id: str = "policy-a",
) -> RoutingPolicy:
    return RoutingPolicy(
        policy_id=policy_id,
        ordered_target_ids=("target-a",),
    )


def _routing_decision(
    *,
    policy_id: str = "policy-a",
    status: RoutingDecisionStatus = (
        RoutingDecisionStatus.SELECTED
    ),
) -> RoutingDecision:
    if status is RoutingDecisionStatus.SELECTED:
        return RoutingDecision(
            policy_id=policy_id,
            status=status,
            reason=(
                RoutingDecisionReason.PRIMARY_SELECTED
            ),
            selected_target_id="target-a",
            candidates=(
                RoutingCandidate(
                    target_id="target-a",
                    eligible=True,
                ),
            ),
        )

    return RoutingDecision(
        policy_id=policy_id,
        status=status,
        reason=(
            RoutingDecisionReason.NO_ELIGIBLE_TARGET
        ),
        candidates=(
            RoutingCandidate(
                target_id="target-a",
                eligible=False,
                ineligibility_reasons=(
                    "target_disabled",
                ),
            ),
        ),
    )


def _routing_record(
    *,
    evidence_id: str,
    observed_at: datetime,
    policy_id: str = "policy-a",
    execution_outcome: RoutingEvidenceExecutionOutcome = (
        RoutingEvidenceExecutionOutcome.SUCCEEDED
    ),
) -> RoutingEvidenceRecord:
    if (
        execution_outcome
        is RoutingEvidenceExecutionOutcome.NOT_EXECUTED
    ):
        return RoutingEvidenceRecord(
            evidence_id=evidence_id,
            policy=_routing_policy(
                policy_id=policy_id
            ),
            decision=_routing_decision(
                policy_id=policy_id,
                status=(
                    RoutingDecisionStatus.NO_ELIGIBLE_TARGET
                ),
            ),
            execution_outcome=execution_outcome,
            observed_at=observed_at,
        )

    if (
        execution_outcome
        is RoutingEvidenceExecutionOutcome.FAILED
    ):
        return RoutingEvidenceRecord(
            evidence_id=evidence_id,
            policy=_routing_policy(
                policy_id=policy_id
            ),
            decision=_routing_decision(
                policy_id=policy_id
            ),
            execution_outcome=execution_outcome,
            attempts=(
                RoutingExecutionAttemptEvidence(
                    target_id="target-a",
                    outcome=(
                        RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
                    ),
                    failure_category="transport",
                ),
            ),
            observed_at=observed_at,
        )

    return RoutingEvidenceRecord(
        evidence_id=evidence_id,
        policy=_routing_policy(
            policy_id=policy_id
        ),
        decision=_routing_decision(
            policy_id=policy_id
        ),
        execution_outcome=execution_outcome,
        executed_target_id="target-a",
        attempts=(
            RoutingExecutionAttemptEvidence(
                target_id="target-a",
                outcome=(
                    RoutingEvidenceAttemptOutcome.SUCCEEDED
                ),
            ),
        ),
        observed_at=observed_at,
    )


def _run(
    *,
    run_id: str,
    dataset_id: str = "dataset-a",
    dataset_version: str = "v1",
    target_id: str = "target-a",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
) -> EvaluationRunRecord:
    identity = EvaluationRunIdentity(
        run_id=run_id,
        dataset=EvaluationDatasetIdentity(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
        ),
        target_id=target_id,
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
                    value=0.5,
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
                value=0.0,
            ),
        ),
    )


def _gate_result(
    *,
    run_id: str,
    gate_id: str,
) -> EvaluationGateResult:
    return EvaluationGateResult(
        gate=EvaluationQualityGate(
            gate_id=gate_id,
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
        decision=EvaluationGateDecision.PASSED,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                value=0.0,
            ),
        ),
    )


def _evaluation_record(
    *,
    evidence_id: str,
    run_id: str,
    observed_at: datetime,
    dataset_id: str = "dataset-a",
    dataset_version: str = "v1",
    target_id: str = "target-a",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
    gate_id: str | None = None,
) -> EvaluationEvidenceRecord:
    run = _run(
        run_id=run_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        target_id=target_id,
        outcome=outcome,
    )

    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=run,
        gate_result=(
            _gate_result(
                run_id=run_id,
                gate_id=gate_id,
            )
            if gate_id is not None
            else None
        ),
        observed_at=observed_at,
    )


RoutingFactory = Callable[
    [],
    RoutingEvidenceRepository,
]
EvaluationFactory = Callable[
    [],
    EvaluationEvidenceRepository,
]


@pytest.fixture(
    params=["memory", "sqlite"]
)
def routing_repository(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> RoutingEvidenceRepository:
    if request.param == "memory":
        return InMemoryRoutingEvidenceRepository()

    return SQLiteRoutingEvidenceRepository(
        database_path=tmp_path / "routing.db"
    )


@pytest.fixture(
    params=["memory", "sqlite"]
)
def evaluation_repository(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> EvaluationEvidenceRepository:
    if request.param == "memory":
        return InMemoryEvaluationEvidenceRepository()

    return SQLiteEvaluationEvidenceRepository(
        database_path=tmp_path / "evaluation.db"
    )


def test_routing_create_and_get_round_trip(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    record = _routing_record(
        evidence_id="routing-1",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
    )

    created = routing_repository.create(record)

    assert created == record
    assert (
        routing_repository.get("routing-1")
        == record
    )


def test_routing_missing_get_returns_none(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    assert routing_repository.get("missing") is None


def test_routing_duplicate_is_rejected(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    record = _routing_record(
        evidence_id="routing-duplicate",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
    )

    routing_repository.create(record)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        routing_repository.create(record)


def test_routing_list_is_chronological_then_identity(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    records = (
        _routing_record(
            evidence_id="routing-c",
            observed_at=instant + timedelta(minutes=1),
        ),
        _routing_record(
            evidence_id="routing-b",
            observed_at=instant,
        ),
        _routing_record(
            evidence_id="routing-a",
            observed_at=instant,
        ),
    )

    for record in records:
        routing_repository.create(record)

    assert tuple(
        record.evidence_id
        for record in routing_repository.list_records()
    ) == (
        "routing-a",
        "routing-b",
        "routing-c",
    )


def test_routing_order_normalizes_timezones(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    earlier = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )
    later_with_offset = datetime(
        2026,
        8,
        17,
        6,
        30,
        tzinfo=timezone(
            -timedelta(hours=6)
        ),
    )

    routing_repository.create(
        _routing_record(
            evidence_id="earlier",
            observed_at=earlier,
        )
    )
    routing_repository.create(
        _routing_record(
            evidence_id="later",
            observed_at=later_with_offset,
        )
    )

    assert tuple(
        record.evidence_id
        for record in routing_repository.list_records()
    ) == ("earlier", "later")


def test_routing_filters_compose(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    routing_repository.create(
        _routing_record(
            evidence_id="match",
            observed_at=instant,
            policy_id="policy-a",
        )
    )
    routing_repository.create(
        _routing_record(
            evidence_id="other-policy",
            observed_at=instant,
            policy_id="policy-b",
        )
    )
    routing_repository.create(
        _routing_record(
            evidence_id="failed",
            observed_at=instant,
            policy_id="policy-a",
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.FAILED
            ),
        )
    )

    results = routing_repository.list_records(
        policy_id="policy-a",
        decision_status=(
            RoutingDecisionStatus.SELECTED
        ),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="target-a",
    )

    assert tuple(
        record.evidence_id
        for record in results
    ) == ("match",)


@pytest.mark.parametrize(
    "limit",
    [0, 10001],
)
def test_routing_invalid_list_limit_rejected(
    routing_repository: RoutingEvidenceRepository,
    limit: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 1 and 10000",
    ):
        routing_repository.list_records(
            limit=limit
        )


def test_routing_list_limit_applied_after_ordering(
    routing_repository: RoutingEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    for evidence_id in (
        "routing-c",
        "routing-a",
        "routing-b",
    ):
        routing_repository.create(
            _routing_record(
                evidence_id=evidence_id,
                observed_at=instant,
            )
        )

    assert tuple(
        record.evidence_id
        for record in routing_repository.list_records(
            limit=2
        )
    ) == ("routing-a", "routing-b")


def test_evaluation_create_and_get_round_trip(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    record = _evaluation_record(
        evidence_id="evaluation-1",
        run_id="run-1",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
        gate_id="gate-1",
    )

    created = evaluation_repository.create(record)

    assert created == record
    assert (
        evaluation_repository.get("evaluation-1")
        == record
    )


def test_evaluation_missing_get_returns_none(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    assert evaluation_repository.get("missing") is None


def test_evaluation_duplicate_is_rejected(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    record = _evaluation_record(
        evidence_id="evaluation-duplicate",
        run_id="run-duplicate",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
    )

    evaluation_repository.create(record)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        evaluation_repository.create(record)


def test_evaluation_list_is_chronological_then_identity(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    records = (
        _evaluation_record(
            evidence_id="evaluation-c",
            run_id="run-c",
            observed_at=instant + timedelta(minutes=1),
        ),
        _evaluation_record(
            evidence_id="evaluation-b",
            run_id="run-b",
            observed_at=instant,
        ),
        _evaluation_record(
            evidence_id="evaluation-a",
            run_id="run-a",
            observed_at=instant,
        ),
    )

    for record in records:
        evaluation_repository.create(record)

    assert tuple(
        record.evidence_id
        for record in evaluation_repository.list_records()
    ) == (
        "evaluation-a",
        "evaluation-b",
        "evaluation-c",
    )


def test_evaluation_order_normalizes_timezones(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    earlier = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )
    later_with_offset = datetime(
        2026,
        8,
        17,
        6,
        30,
        tzinfo=timezone(
            -timedelta(hours=6)
        ),
    )

    evaluation_repository.create(
        _evaluation_record(
            evidence_id="earlier",
            run_id="run-earlier",
            observed_at=earlier,
        )
    )
    evaluation_repository.create(
        _evaluation_record(
            evidence_id="later",
            run_id="run-later",
            observed_at=later_with_offset,
        )
    )

    assert tuple(
        record.evidence_id
        for record in evaluation_repository.list_records()
    ) == ("earlier", "later")


def test_evaluation_filters_compose(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    evaluation_repository.create(
        _evaluation_record(
            evidence_id="match",
            run_id="run-match",
            observed_at=instant,
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-a",
            gate_id="gate-a",
        )
    )

    evaluation_repository.create(
        _evaluation_record(
            evidence_id="other-target",
            run_id="run-other-target",
            observed_at=instant,
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-b",
            gate_id="gate-a",
        )
    )

    evaluation_repository.create(
        _evaluation_record(
            evidence_id="failed-run",
            run_id="run-failed",
            observed_at=instant,
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-a",
            outcome=EvaluationRunOutcome.FAILED,
        )
    )

    results = evaluation_repository.list_records(
        run_id="run-match",
        dataset_id="dataset-a",
        dataset_version="v2",
        target_id="target-a",
        run_outcome=EvaluationRunOutcome.SUCCEEDED,
        gate_id="gate-a",
    )

    assert tuple(
        record.evidence_id
        for record in results
    ) == ("match",)


def test_evaluation_gate_filter_excludes_no_gate(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    evaluation_repository.create(
        _evaluation_record(
            evidence_id="with-gate",
            run_id="run-with-gate",
            observed_at=instant,
            gate_id="gate-a",
        )
    )
    evaluation_repository.create(
        _evaluation_record(
            evidence_id="without-gate",
            run_id="run-without-gate",
            observed_at=instant,
        )
    )

    assert tuple(
        record.evidence_id
        for record in evaluation_repository.list_records(
            gate_id="gate-a"
        )
    ) == ("with-gate",)


@pytest.mark.parametrize(
    "limit",
    [0, 10001],
)
def test_evaluation_invalid_list_limit_rejected(
    evaluation_repository: EvaluationEvidenceRepository,
    limit: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 1 and 10000",
    ):
        evaluation_repository.list_records(
            limit=limit
        )


def test_evaluation_list_limit_applied_after_ordering(
    evaluation_repository: EvaluationEvidenceRepository,
) -> None:
    instant = datetime(
        2026, 8, 17, 12, tzinfo=UTC
    )

    for evidence_id in (
        "evaluation-c",
        "evaluation-a",
        "evaluation-b",
    ):
        evaluation_repository.create(
            _evaluation_record(
                evidence_id=evidence_id,
                run_id=f"run-{evidence_id}",
                observed_at=instant,
            )
        )

    assert tuple(
        record.evidence_id
        for record in evaluation_repository.list_records(
            limit=2
        )
    ) == (
        "evaluation-a",
        "evaluation-b",
    )


def test_routing_and_evaluation_identity_namespaces_are_separate(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "shared.db"

    routing = SQLiteRoutingEvidenceRepository(
        database_path=database_path
    )
    evaluation = SQLiteEvaluationEvidenceRepository(
        database_path=database_path
    )

    routing_record = _routing_record(
        evidence_id="shared-id",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
    )
    evaluation_record = _evaluation_record(
        evidence_id="shared-id",
        run_id="run-shared",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
    )

    routing.create(routing_record)
    evaluation.create(evaluation_record)

    assert routing.get("shared-id") == routing_record
    assert (
        evaluation.get("shared-id")
        == evaluation_record
    )


def test_sqlite_reopen_preserves_routing_evidence(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "routing-reopen.db"

    first = SQLiteRoutingEvidenceRepository(
        database_path=database_path
    )
    record = _routing_record(
        evidence_id="routing-persisted",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
    )

    first.create(record)

    reopened = SQLiteRoutingEvidenceRepository(
        database_path=database_path
    )

    assert (
        reopened.get("routing-persisted")
        == record
    )


def test_sqlite_reopen_preserves_evaluation_evidence(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evaluation-reopen.db"

    first = SQLiteEvaluationEvidenceRepository(
        database_path=database_path
    )
    record = _evaluation_record(
        evidence_id="evaluation-persisted",
        run_id="run-persisted",
        observed_at=datetime(
            2026, 8, 17, 12, tzinfo=UTC
        ),
        gate_id="gate-persisted",
    )

    first.create(record)

    reopened = SQLiteEvaluationEvidenceRepository(
        database_path=database_path
    )

    assert (
        reopened.get("evaluation-persisted")
        == record
    )
