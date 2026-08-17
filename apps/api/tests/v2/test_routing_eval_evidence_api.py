from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import V2Services
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

client = TestClient(app)


def setup_function() -> None:
    v2_routes.services = V2Services()


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
    policy_id: str = "policy-a",
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
    run_id: str = "run-a",
    dataset_id: str = "dataset-a",
    dataset_version: str = "v1",
    target_id: str = "target-a",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
    observed_minute: int = 0,
) -> EvaluationEvidenceRecord:
    metric_results = (
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
    )

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
        metric_results=metric_results,
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


def test_routing_evidence_get_returns_record() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .routing
    )

    repository.create(
        _routing_record(
            evidence_id="routing-1",
        )
    )

    response = client.get(
        "/api/v2/evidence/routing/routing-1"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["evidence"]["evidence_id"]
        == "routing-1"
    )
    assert (
        body["evidence"]["policy"]["policy_id"]
        == "policy-a"
    )


def test_routing_evidence_get_missing_returns_404() -> None:
    response = client.get(
        "/api/v2/evidence/routing/missing"
    )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_routing_evidence_list_filters_by_policy() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .routing
    )

    repository.create(
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

    response = client.get(
        "/api/v2/evidence/routing",
        params={
            "policy_id": "policy-a",
        },
    )

    assert response.status_code == 200

    records = response.json()["records"]

    assert len(records) == 1
    assert records[0]["evidence_id"] == "routing-a"


def test_routing_evidence_list_accepts_enum_filters() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .routing
    )

    repository.create(
        _routing_record(
            evidence_id="routing-a",
        )
    )

    response = client.get(
        "/api/v2/evidence/routing",
        params={
            "decision_status": "selected",
            "execution_outcome": "not_executed",
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["records"][0]["evidence_id"]
        == "routing-a"
    )


def test_routing_evidence_list_preserves_limit() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .routing
    )

    repository.create(
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

    response = client.get(
        "/api/v2/evidence/routing",
        params={
            "limit": 1,
        },
    )

    assert response.status_code == 200

    records = response.json()["records"]

    assert len(records) == 1
    assert (
        records[0]["evidence_id"]
        == "routing-first"
    )


def test_routing_evidence_invalid_limit_returns_422() -> None:
    response = client.get(
        "/api/v2/evidence/routing",
        params={
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_evaluation_evidence_get_returns_record() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .evaluation
    )

    repository.create(
        _evaluation_record(
            evidence_id="evaluation-1",
        )
    )

    response = client.get(
        "/api/v2/evidence/evaluation/evaluation-1"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["evidence"]["evidence_id"]
        == "evaluation-1"
    )
    assert (
        body["evidence"]["run"]["identity"]["run_id"]
        == "run-a"
    )


def test_evaluation_evidence_get_missing_returns_404() -> None:
    response = client.get(
        "/api/v2/evidence/evaluation/missing"
    )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_evaluation_evidence_list_filters_run() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .evaluation
    )

    repository.create(
        _evaluation_record(
            evidence_id="evaluation-a",
            run_id="run-a",
        )
    )
    repository.create(
        _evaluation_record(
            evidence_id="evaluation-b",
            run_id="run-b",
        )
    )

    response = client.get(
        "/api/v2/evidence/evaluation",
        params={
            "run_id": "run-a",
        },
    )

    assert response.status_code == 200

    records = response.json()["records"]

    assert len(records) == 1
    assert (
        records[0]["evidence_id"]
        == "evaluation-a"
    )


def test_evaluation_evidence_list_filters_dataset_target_outcome() -> None:
    repository = (
        v2_routes.services
        .routing_eval_evidence_repositories
        .evaluation
    )

    repository.create(
        _evaluation_record(
            evidence_id="evaluation-failed",
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-a",
            outcome=EvaluationRunOutcome.FAILED,
        )
    )
    repository.create(
        _evaluation_record(
            evidence_id="evaluation-other",
            dataset_id="dataset-b",
            dataset_version="v1",
            target_id="target-b",
        )
    )

    response = client.get(
        "/api/v2/evidence/evaluation",
        params={
            "dataset_id": "dataset-a",
            "dataset_version": "v2",
            "target_id": "target-a",
            "run_outcome": "failed",
        },
    )

    assert response.status_code == 200

    records = response.json()["records"]

    assert len(records) == 1
    assert (
        records[0]["evidence_id"]
        == "evaluation-failed"
    )


def test_evaluation_evidence_invalid_limit_returns_422() -> None:
    response = client.get(
        "/api/v2/evidence/evaluation",
        params={
            "limit": 10001,
        },
    )

    assert response.status_code == 422


def test_v2_services_recorders_and_queries_share_repositories() -> None:
    services = V2Services()

    run = _evaluation_record(
        evidence_id="unused",
    ).run

    services.evaluation_evidence.record_run(
        evidence_id="shared-evidence",
        run=run,
        observed_at=_observed_at(),
    )

    queried = (
        services.evaluation_evidence_query.get(
            evidence_id="shared-evidence",
        )
    )

    assert queried.evidence_id == "shared-evidence"
