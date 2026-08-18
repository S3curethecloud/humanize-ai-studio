from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.settings import (
    ProviderName,
    Settings,
)
from app.v2.api.dependencies import V2Services
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
from app.v2.services.eval_ops_repository_factory import (
    ExternalEvaluationOpsPersistenceUnavailableError,
    build_evaluation_ops_repositories,
)
from app.workflows.rewrite_workflow import RewriteWorkflow


def _provider_settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )


def _target_settings(
) -> ProviderTargetDeclarationSettings:
    return ProviderTargetDeclarationSettings.from_environment()


def _memory_persistence() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _sqlite_persistence(
    path: Path,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=path,
        database_url=None,
    )


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="container-eval-suite",
        dataset_version="v1",
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=_dataset_identity(),
        cases=(
            EvaluationDatasetCase(
                case_id="case-1",
                input=EvaluationCaseInput(
                    text=(
                        "This is a deterministic evaluation "
                        "sentence for the service container."
                    )
                ),
            ),
        ),
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        23,
        0,
        tzinfo=UTC,
    )


def _services(
    persistence: V2PersistenceSettings,
    monkeypatch,
) -> V2Services:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    return V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=persistence,
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )


def _execute_run(
    services: V2Services,
    *,
    run_id: str,
    evidence_id: str,
):
    return services.evaluation_ops.run_execution.execute(
        evidence_id=evidence_id,
        request=EvaluationRunRequest(
            run_id=run_id,
            dataset=_dataset_identity(),
            target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(),
    )


def test_memory_container_composes_governed_evalops(
    monkeypatch,
) -> None:
    services = _services(
        _memory_persistence(),
        monkeypatch,
    )

    services.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = _execute_run(
        services,
        run_id="memory-eval-run",
        evidence_id="memory-run-evidence",
    )

    assert (
        services.evaluation_ops_repositories.runs.get(
            "memory-eval-run"
        )
        == run
    )

    evidence = services.evaluation_evidence_query.get(
        evidence_id="memory-run-evidence"
    )
    assert evidence.run == run
    assert evidence.gate_result is None


def test_memory_container_records_gate_evidence(
    monkeypatch,
) -> None:
    services = _services(
        _memory_persistence(),
        monkeypatch,
    )

    services.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = _execute_run(
        services,
        run_id="memory-gate-run",
        evidence_id="memory-before-gate",
    )

    result = services.evaluation_ops.quality_gate.evaluate(
        evidence_id="memory-gate-evidence",
        gate=EvaluationQualityGate(
            gate_id="container-gate",
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
        run_id=run.identity.run_id,
        observed_at=_observed_at(),
    )

    assert (
        result.decision
        is EvaluationGateDecision.PASSED
    )

    evidence = services.evaluation_evidence_query.get(
        evidence_id="memory-gate-evidence"
    )
    assert evidence.run == run
    assert evidence.gate_result == result


def test_sqlite_evalops_survives_container_recreation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    persistence = _sqlite_persistence(
        tmp_path / "evalops-container.db"
    )

    first = _services(
        persistence,
        monkeypatch,
    )

    first.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = _execute_run(
        first,
        run_id="sqlite-eval-run",
        evidence_id="sqlite-run-evidence",
    )

    second = _services(
        persistence,
        monkeypatch,
    )

    stored_dataset = (
        second.evaluation_ops_repositories.datasets.get(
            _dataset_identity()
        )
    )
    stored_run = (
        second.evaluation_ops_repositories.runs.get(
            "sqlite-eval-run"
        )
    )
    evidence = second.evaluation_evidence_query.get(
        evidence_id="sqlite-run-evidence"
    )

    assert stored_dataset == _dataset()
    assert stored_run == run
    assert evidence.run == run


def test_evalops_uses_same_provider_catalog_identity(
    monkeypatch,
) -> None:
    services = _services(
        _memory_persistence(),
        monkeypatch,
    )

    assert (
        services.provider_routing.catalog
        is services.provider_catalog
    )

    target = services.provider_catalog.get(
        DEFAULT_DETERMINISTIC_TARGET_ID
    )
    assert target is not None

    services.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = _execute_run(
        services,
        run_id="catalog-identity-run",
        evidence_id="catalog-identity-evidence",
    )

    assert (
        run.identity.target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )


def test_external_evalops_repository_factory_fails_closed() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url="postgresql://example.invalid/test",
    )

    with pytest.raises(
        ExternalEvaluationOpsPersistenceUnavailableError,
        match="no external EvalOps adapter",
    ):
        build_evaluation_ops_repositories(
            settings
        )
