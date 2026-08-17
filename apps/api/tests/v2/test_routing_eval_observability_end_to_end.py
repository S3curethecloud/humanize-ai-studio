from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.observability.metrics import metrics_registry
from app.observability.metrics_access import (
    METRICS_BEARER_TOKEN_ENV,
)
from app.providers.exceptions import (
    RewriteProviderTransportError,
)
from app.v2.api.dependencies import V2Services
from app.v2.api.evidence_access import (
    EVIDENCE_BEARER_TOKEN_ENV,
)
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
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttempt,
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionFailureResult,
)

client = TestClient(app)

EVIDENCE_TOKEN = "h7b-evidence-token"
METRICS_TOKEN = "h7b-metrics-token"


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        14,
        0,
        tzinfo=UTC,
    )


def setup_function() -> None:
    metrics_registry.reset_for_tests()

    os.environ[
        EVIDENCE_BEARER_TOKEN_ENV
    ] = EVIDENCE_TOKEN

    os.environ[
        METRICS_BEARER_TOKEN_ENV
    ] = METRICS_TOKEN

    v2_routes.services = V2Services()


def teardown_function() -> None:
    metrics_registry.reset_for_tests()

    os.environ.pop(
        EVIDENCE_BEARER_TOKEN_ENV,
        None,
    )
    os.environ.pop(
        METRICS_BEARER_TOKEN_ENV,
        None,
    )


def _evidence_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {EVIDENCE_TOKEN}",
    }


def _metrics_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {METRICS_TOKEN}",
    }


def _routing_inputs() -> tuple[
    RoutingPolicy,
    RoutingDecision,
    ProviderRoutingExecutionFailureResult,
]:
    policy = RoutingPolicy(
        policy_id="policy-e2e",
        ordered_target_ids=("target-e2e",),
    )

    decision = RoutingDecision(
        policy_id=policy.policy_id,
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="target-e2e",
        candidates=(
            RoutingCandidate(
                target_id="target-e2e",
                eligible=True,
            ),
        ),
    )

    outcome = ProviderRoutingExecutionFailureResult(
        error=RewriteProviderTransportError(
            "transport failure"
        ),
        initial_target_id="target-e2e",
        attempts=(
            ProviderExecutionAttempt(
                target_id="target-e2e",
                outcome=(
                    ProviderExecutionAttemptOutcome.PROVIDER_ERROR
                ),
                failure_category=(
                    RoutingFailureCategory.TRANSPORT
                ),
            ),
        ),
    )

    return policy, decision, outcome


def _evaluation_run() -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id="run-e2e",
            dataset=EvaluationDatasetIdentity(
                dataset_id="dataset-e2e",
                dataset_version="v1",
            ),
            target_id="target-e2e",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=3,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                value=0.93,
            ),
            EvaluationMetricResult(
                metric=EvaluationMetric.PROVIDER_ERROR_RATE,
                value=0.0,
            ),
        ),
    )


def test_routing_evidence_flows_from_recorder_to_api_and_metrics() -> None:
    policy, decision, outcome = _routing_inputs()

    persisted = (
        v2_routes.services
        .routing_execution_evidence
        .record(
            evidence_id="routing-e2e",
            policy=policy,
            decision=decision,
            outcome=outcome,
            observed_at=_observed_at(),
        )
    )

    queried = client.get(
        "/api/v2/evidence/routing/routing-e2e",
        headers=_evidence_headers(),
    )

    assert queried.status_code == 200

    body = queried.json()["evidence"]

    assert body["evidence_id"] == persisted.evidence_id
    assert body["policy"]["policy_id"] == "policy-e2e"
    assert body["execution_outcome"] == "failed"
    assert body["executed_target_id"] is None

    metrics = client.get(
        "/metrics",
        headers=_metrics_headers(),
    )

    assert metrics.status_code == 200

    rendered = metrics.text

    assert (
        'humanize_v2_routing_decisions_total'
        '{status="selected",reason="primary_selected"} 1'
        in rendered
    )
    assert (
        'humanize_v2_routing_executions_total'
        '{outcome="failed",fallback_used="false"} 1'
        in rendered
    )
    assert (
        'humanize_v2_routing_attempts_total'
        '{outcome="provider_error",'
        'failure_category="transport"} 1'
        in rendered
    )


def test_eval_evidence_flows_from_recorder_to_api_and_metrics() -> None:
    persisted = (
        v2_routes.services
        .evaluation_evidence
        .record_run(
            evidence_id="evaluation-e2e",
            run=_evaluation_run(),
            observed_at=_observed_at(),
        )
    )

    queried = client.get(
        "/api/v2/evidence/evaluation/evaluation-e2e",
        headers=_evidence_headers(),
    )

    assert queried.status_code == 200

    body = queried.json()["evidence"]

    assert body["evidence_id"] == persisted.evidence_id
    assert (
        body["run"]["identity"]["run_id"]
        == "run-e2e"
    )
    assert body["run"]["outcome"] == "succeeded"
    assert body["run"]["evaluated_case_count"] == 3

    metrics = client.get(
        "/metrics",
        headers=_metrics_headers(),
    )

    assert metrics.status_code == 200

    rendered = metrics.text

    assert (
        'humanize_v2_eval_runs_total'
        '{outcome="succeeded"} 1'
        in rendered
    )
    assert (
        'humanize_v2_eval_cases_total'
        '{outcome="evaluated"} 3'
        in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_sum'
        '{metric="claim_preservation"} 0.930000000'
        in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_count'
        '{metric="claim_preservation"} 1'
        in rendered
    )


def test_evidence_and_metrics_access_boundaries_are_distinct() -> None:
    evidence_with_metrics_token = client.get(
        "/api/v2/evidence/evaluation",
        headers=_metrics_headers(),
    )

    assert evidence_with_metrics_token.status_code == 403
    assert (
        evidence_with_metrics_token.json()["detail"]
        == "evidence authorization failed"
    )

    metrics_with_evidence_token = client.get(
        "/metrics",
        headers=_evidence_headers(),
    )

    assert metrics_with_evidence_token.status_code == 403
    assert (
        metrics_with_evidence_token.json()["detail"]
        == "metrics authorization failed"
    )
