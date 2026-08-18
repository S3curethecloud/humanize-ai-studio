from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.core.settings import (
    ProviderName,
    Settings,
)
from app.domain.models import RewriteRequest
from app.main import app
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

EVIDENCE_TOKEN = "h7c3b-evidence-token"


def _provider_settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )


def _targets(
) -> ProviderTargetDeclarationSettings:
    return ProviderTargetDeclarationSettings.from_environment()


def _persistence(
    path: Path,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=path,
        database_url=None,
    )


def _services(
    path: Path,
) -> V2Services:
    os.environ.pop(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        None,
    )

    return V2Services(
        persistence_settings=_persistence(path),
        provider_settings=_provider_settings(),
        provider_target_settings=_targets(),
    )


def _observed_at(
    *,
    hour: int,
) -> datetime:
    return datetime(
        2026,
        8,
        18,
        hour,
        0,
        tzinfo=UTC,
    )


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="h7c3b-sqlite-suite",
        dataset_version="v1",
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=_dataset_identity(),
        cases=(
            EvaluationDatasetCase(
                case_id="h7c3b-case",
                input=EvaluationCaseInput(
                    text=(
                        "This deterministic evaluation "
                        "must survive service reconstruction."
                    ),
                ),
            ),
        ),
    )


def _evidence_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {EVIDENCE_TOKEN}",
    }


def setup_function() -> None:
    os.environ[
        EVIDENCE_BEARER_TOKEN_ENV
    ] = EVIDENCE_TOKEN


def teardown_function() -> None:
    os.environ.pop(
        EVIDENCE_BEARER_TOKEN_ENV,
        None,
    )


def test_sqlite_routing_evidence_survives_service_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "routing-restart.db"

    first = _services(database)

    result = first.provider_routing.routing.route_and_execute(
        evidence_id="h7c3b-routing-evidence",
        policy=RoutingPolicy(
            policy_id="h7c3b-routing-policy",
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
        observed_at=_observed_at(hour=1),
    )

    assert (
        result.execution.executed_target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )

    second = _services(database)

    assert (
        second.provider_catalog_provisioning_result
        .created_target_ids
        == ()
    )

    persisted = second.routing_evidence_query.get(
        evidence_id="h7c3b-routing-evidence"
    )

    assert (
        persisted.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )
    assert (
        persisted.executed_target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )

    v2_routes.services = second

    response = client.get(
        "/api/v2/evidence/routing/"
        "h7c3b-routing-evidence",
        headers=_evidence_headers(),
    )

    assert response.status_code == 200

    body = response.json()["evidence"]

    assert (
        body["execution_outcome"]
        == RoutingEvidenceExecutionOutcome.SUCCEEDED.value
    )
    assert (
        body["executed_target_id"]
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )


def test_sqlite_eval_run_and_evidence_survive_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "eval-restart.db"

    first = _services(database)

    first.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = first.evaluation_ops.run_execution.execute(
        evidence_id="h7c3b-run-evidence",
        request=EvaluationRunRequest(
            run_id="h7c3b-run",
            dataset=_dataset_identity(),
            target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(hour=2),
    )

    second = _services(database)

    persisted_dataset = (
        second.evaluation_ops_repositories.datasets.get(
            _dataset_identity()
        )
    )
    persisted_run = (
        second.evaluation_ops_repositories.runs.get(
            "h7c3b-run"
        )
    )
    persisted_evidence = (
        second.evaluation_evidence_query.get(
            evidence_id="h7c3b-run-evidence"
        )
    )

    assert persisted_dataset == _dataset()
    assert persisted_run == run
    assert persisted_evidence.run == run
    assert persisted_evidence.gate_result is None

    v2_routes.services = second

    response = client.get(
        "/api/v2/evidence/evaluation/"
        "h7c3b-run-evidence",
        headers=_evidence_headers(),
    )

    assert response.status_code == 200

    body = response.json()["evidence"]

    assert (
        body["run"]["identity"]["run_id"]
        == "h7c3b-run"
    )
    assert body["gate_result"] is None


def test_restarted_evalops_can_gate_persisted_run(
    tmp_path: Path,
) -> None:
    database = tmp_path / "gate-restart.db"

    first = _services(database)

    first.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = first.evaluation_ops.run_execution.execute(
        evidence_id="h7c3b-run-before-restart",
        request=EvaluationRunRequest(
            run_id="h7c3b-gate-run",
            dataset=_dataset_identity(),
            target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(hour=3),
    )

    second = _services(database)

    gate_result = (
        second.evaluation_ops.quality_gate.evaluate(
            evidence_id="h7c3b-gate-evidence",
            gate=EvaluationQualityGate(
                gate_id="h7c3b-gate",
                thresholds=(
                    EvaluationThreshold(
                        metric=(
                            EvaluationMetric
                            .PROVIDER_ERROR_RATE
                        ),
                        comparator=(
                            EvaluationComparator.AT_MOST
                        ),
                        threshold=0.0,
                    ),
                ),
            ),
            run_id=run.identity.run_id,
            observed_at=_observed_at(hour=4),
        )
    )

    assert (
        gate_result.decision
        is EvaluationGateDecision.PASSED
    )

    persisted_gate_evidence = (
        second.evaluation_evidence_query.get(
            evidence_id="h7c3b-gate-evidence"
        )
    )

    assert persisted_gate_evidence.run == run
    assert (
        persisted_gate_evidence.gate_result
        == gate_result
    )

    third = _services(database)

    third_gate_evidence = (
        third.evaluation_evidence_query.get(
            evidence_id="h7c3b-gate-evidence"
        )
    )

    assert third_gate_evidence == persisted_gate_evidence

    v2_routes.services = third

    response = client.get(
        "/api/v2/evidence/evaluation/"
        "h7c3b-gate-evidence",
        headers=_evidence_headers(),
    )

    assert response.status_code == 200

    body = response.json()["evidence"]

    assert (
        body["run"]["identity"]["run_id"]
        == "h7c3b-gate-run"
    )
    assert (
        body["gate_result"]["decision"]
        == EvaluationGateDecision.PASSED.value
    )


def test_restart_does_not_require_direct_evidence_replay(
    tmp_path: Path,
) -> None:
    database = tmp_path / "no-replay.db"

    first = _services(database)

    first.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    first.evaluation_ops.run_execution.execute(
        evidence_id="h7c3b-no-replay-evidence",
        request=EvaluationRunRequest(
            run_id="h7c3b-no-replay-run",
            dataset=_dataset_identity(),
            target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(hour=5),
    )

    second = _services(database)

    evidence = second.evaluation_evidence_query.get(
        evidence_id="h7c3b-no-replay-evidence"
    )
    run = second.evaluation_ops_repositories.runs.get(
        "h7c3b-no-replay-run"
    )

    assert evidence.run == run
    assert evidence.evidence_id == (
        "h7c3b-no-replay-evidence"
    )
