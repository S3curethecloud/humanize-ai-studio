from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.settings import (
    ProviderName,
    Settings,
)
from app.domain.models import RewriteRequest
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    DEFAULT_DETERMINISTIC_TARGET_ID,
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
    RoutingDecisionStatus,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
)
from app.v2.services.governed_provider_routing_service import (
    ProviderRoutingSelectedResult,
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


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        19,
        0,
        tzinfo=UTC,
    )


def _execute_default_route(
    services: V2Services,
    *,
    evidence_id: str,
) -> ProviderRoutingSelectedResult:
    result = services.provider_routing.routing.route_and_execute(
        evidence_id=evidence_id,
        policy=RoutingPolicy(
            policy_id="default-deterministic",
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

    assert isinstance(
        result,
        ProviderRoutingSelectedResult,
    )
    return result


def test_memory_container_composes_canonical_routing_runtime(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )

    assert (
        services.provider_routing.catalog
        is services.provider_catalog
    )
    assert (
        services.routing_execution_evidence
        is services.provider_routing.execution_evidence
    )
    assert (
        services.routing_decision_evidence
        is services.provider_routing.decision_evidence
    )

    target = services.provider_catalog.get(
        DEFAULT_DETERMINISTIC_TARGET_ID
    )
    assert target is not None
    assert target.enabled is True

    result = _execute_default_route(
        services,
        evidence_id="container-memory-route",
    )

    assert (
        result.decision.status
        is RoutingDecisionStatus.SELECTED
    )

    record = services.routing_evidence_query.get(
        evidence_id="container-memory-route"
    )
    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )
    assert (
        record.executed_target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )


def test_sqlite_container_reprovisions_idempotently_and_queries_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    persistence = _sqlite_persistence(
        tmp_path / "routing-container.db"
    )
    targets = _target_settings()
    provider_settings = _provider_settings()

    first = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=persistence,
        provider_settings=provider_settings,
        provider_target_settings=targets,
    )

    assert (
        first.provider_catalog_provisioning_result
        .created_target_ids
        == (
            DEFAULT_DETERMINISTIC_TARGET_ID,
        )
    )

    _execute_default_route(
        first,
        evidence_id="container-sqlite-route",
    )

    second = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=persistence,
        provider_settings=provider_settings,
        provider_target_settings=targets,
    )

    assert (
        second.provider_catalog_provisioning_result
        .created_target_ids
        == ()
    )

    target = second.provider_catalog.get(
        DEFAULT_DETERMINISTIC_TARGET_ID
    )
    assert target is not None

    record = second.routing_evidence_query.get(
        evidence_id="container-sqlite-route"
    )
    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )


def test_injected_workflow_does_not_replace_routing_runtime(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    workflow = RewriteWorkflow()

    services = V2Services(
        workflow=workflow,
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )

    result = _execute_default_route(
        services,
        evidence_id="container-independent-route",
    )

    assert (
        result.execution.executed_target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )


def test_container_default_target_is_exactly_one_deterministic_target(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )

    targets = services.provider_catalog.list_targets(
        enabled_only=False,
        limit=10_000,
    )

    assert tuple(
        target.target_id
        for target in targets
    ) == (
        DEFAULT_DETERMINISTIC_TARGET_ID,
    )
