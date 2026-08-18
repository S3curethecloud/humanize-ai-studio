from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.core.settings import (
    ProviderName,
    Settings,
)
from app.domain.models import RewriteRequest
from app.main import app
from app.observability.metrics import metrics_registry
from app.observability.metrics_access import (
    METRICS_BEARER_TOKEN_ENV,
)
from app.v2.api.dependencies import V2Services
from app.v2.api.evidence_access import (
    EVIDENCE_BEARER_TOKEN_ENV,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    DEFAULT_DETERMINISTIC_TARGET_ID,
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationDataset,
    EvaluationDatasetCase,
)
from app.v2.domain.eval_execution import (
    EvaluationRunRequest,
)
from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationDatasetIdentity,
    EvaluationGateDecision,
    EvaluationMetric,
    EvaluationQualityGate,
    EvaluationThreshold,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
)

client = TestClient(app)

EVIDENCE_TOKEN = "h7c3a-evidence-token"
METRICS_TOKEN = "h7c3a-metrics-token"


def _provider_settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )


def _persistence() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _targets(
) -> ProviderTargetDeclarationSettings:
    return ProviderTargetDeclarationSettings.from_environment()


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        18,
        0,
        0,
        tzinfo=UTC,
    )


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="h7c3a-suite",
        dataset_version="v1",
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=_dataset_identity(),
        cases=(
            EvaluationDatasetCase(
                case_id="h7c3a-case",
                input=EvaluationCaseInput(
                    text=(
                        "This is a deterministic composed "
                        "runtime evaluation sentence."
                    ),
                ),
            ),
        ),
    )


def _evidence_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {EVIDENCE_TOKEN}",
    }


def _metrics_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {METRICS_TOKEN}",
    }


def setup_function() -> None:
    metrics_registry.reset_for_tests()

    os.environ[
        EVIDENCE_BEARER_TOKEN_ENV
    ] = EVIDENCE_TOKEN

    os.environ[
        METRICS_BEARER_TOKEN_ENV
    ] = METRICS_TOKEN

    os.environ.pop(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        None,
    )

    v2_routes.services = V2Services(
        persistence_settings=_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_targets(),
    )


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


def test_composed_routing_runtime_flows_to_api_and_metrics() -> None:
    result = (
        v2_routes.services
        .provider_routing
        .routing
        .route_and_execute(
            evidence_id="h7c3a-routing-evidence",
            policy=RoutingPolicy(
                policy_id="h7c3a-routing-policy",
                ordered_target_ids=(
                    DEFAULT_DETERMINISTIC_TARGET_ID,
                ),
            ),
            requirement=RoutingRequirement(
                required_capabilities=frozenset(
                    {
                        ProviderCapability.REWRITE,
                    }
                ),
            ),
            request=RewriteRequest(
                text="Furthermore, this is direct.",
            ),
            observed_at=_observed_at(),
        )
    )

    assert (
        result.execution.executed_target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )

    queried = client.get(
        "/api/v2/evidence/routing/"
        "h7c3a-routing-evidence",
        headers=_evidence_headers(),
    )

    assert queried.status_code == 200

    evidence = queried.json()["evidence"]

    assert (
        evidence["execution_outcome"]
        == RoutingEvidenceExecutionOutcome.SUCCEEDED.value
    )
    assert (
        evidence["executed_target_id"]
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )

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
        '{outcome="succeeded",fallback_used="false"} 1'
        in rendered
    )
    assert (
        'humanize_v2_routing_attempts_total'
        '{outcome="succeeded",failure_category="none"} 1'
        in rendered
    )


def test_composed_evalops_run_and_gate_flow_to_api_and_metrics() -> None:
    services = v2_routes.services

    services.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = services.evaluation_ops.run_execution.execute(
        evidence_id="h7c3a-run-evidence",
        request=EvaluationRunRequest(
            run_id="h7c3a-run",
            dataset=_dataset_identity(),
            target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(),
    )

    gate = EvaluationQualityGate(
        gate_id="h7c3a-gate",
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

    gate_result = (
        services.evaluation_ops.quality_gate.evaluate(
            evidence_id="h7c3a-gate-evidence",
            gate=gate,
            run_id=run.identity.run_id,
            observed_at=_observed_at(),
        )
    )

    assert (
        gate_result.decision
        is EvaluationGateDecision.PASSED
    )

    run_query = client.get(
        "/api/v2/evidence/evaluation/"
        "h7c3a-run-evidence",
        headers=_evidence_headers(),
    )

    assert run_query.status_code == 200

    run_evidence = run_query.json()["evidence"]

    assert (
        run_evidence["run"]["identity"]["run_id"]
        == "h7c3a-run"
    )
    assert run_evidence["gate_result"] is None

    gate_query = client.get(
        "/api/v2/evidence/evaluation/"
        "h7c3a-gate-evidence",
        headers=_evidence_headers(),
    )

    assert gate_query.status_code == 200

    gate_evidence = gate_query.json()["evidence"]

    assert (
        gate_evidence["run"]["identity"]["run_id"]
        == "h7c3a-run"
    )
    assert (
        gate_evidence["gate_result"]["decision"]
        == EvaluationGateDecision.PASSED.value
    )

    metrics = client.get(
        "/metrics",
        headers=_metrics_headers(),
    )

    assert metrics.status_code == 200

    rendered = metrics.text

    assert (
        'humanize_v2_eval_runs_total'
        '{outcome="succeeded"} 2'
        in rendered
    )
    assert (
        'humanize_v2_eval_cases_total'
        '{outcome="evaluated"} 2'
        in rendered
    )
    assert (
        'humanize_v2_eval_gate_decisions_total'
        '{decision="passed"} 1'
        in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_count'
        '{metric="provider_error_rate"} 2'
        in rendered
    )


def test_operator_tokens_remain_independent() -> None:
    evidence_with_metrics_token = client.get(
        "/api/v2/evidence/evaluation",
        headers=_metrics_headers(),
    )

    assert evidence_with_metrics_token.status_code == 403

    metrics_with_evidence_token = client.get(
        "/metrics",
        headers=_evidence_headers(),
    )

    assert metrics_with_evidence_token.status_code == 403


def test_prometheus_does_not_expose_high_cardinality_ids() -> None:
    services = v2_routes.services

    services.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    services.evaluation_ops.run_execution.execute(
        evidence_id="secret-evidence-id-h7c3a",
        request=EvaluationRunRequest(
            run_id="secret-run-id-h7c3a",
            dataset=_dataset_identity(),
            target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(),
    )

    metrics = client.get(
        "/metrics",
        headers=_metrics_headers(),
    )

    assert metrics.status_code == 200

    rendered = metrics.text

    assert "secret-evidence-id-h7c3a" not in rendered
    assert "secret-run-id-h7c3a" not in rendered
    assert DEFAULT_DETERMINISTIC_TARGET_ID not in rendered
    assert "h7c3a-suite" not in rendered
    assert "h7c3a-case" not in rendered
