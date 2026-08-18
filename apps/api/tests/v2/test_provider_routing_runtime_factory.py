from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.core.settings import ProviderName, Settings
from app.domain.models import RewriteRequest
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
    RoutingDecisionStatus,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
    ProviderCatalogRepository,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.governed_provider_routing_service import (
    ProviderRoutingNotExecutedResult,
    ProviderRoutingSelectedResult,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)
from app.v2.services.provider_routing_runtime_factory import (
    ProviderRoutingRuntimeCompositionError,
    build_provider_routing_runtime,
)


def _settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )


def _target(
    *,
    target_id: str = "deterministic-primary",
    enabled: bool = True,
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=DETERMINISTIC_PROVIDER_ID,
            display_name="Deterministic",
        ),
        model=ModelIdentity(
            provider_id=DETERMINISTIC_PROVIDER_ID,
            model_id=DETERMINISTIC_MODEL_ID,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        ),
        enabled=enabled,
    )


def _catalog(
    *,
    enabled: bool = True,
) -> InMemoryProviderCatalogRepository:
    catalog = InMemoryProviderCatalogRepository()
    catalog.create(
        _target(
            enabled=enabled,
        )
    )
    return catalog


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        18,
        0,
        tzinfo=UTC,
    )


def test_factory_composes_selected_routing_end_to_end() -> None:
    catalog = _catalog()
    evidence = InMemoryRoutingEvidenceRepository()

    runtime = build_provider_routing_runtime(
        settings=_settings(),
        catalog=catalog,
        evidence=evidence,
    )

    result = runtime.routing.route_and_execute(
        evidence_id="routing-runtime-selected",
        policy=RoutingPolicy(
            policy_id="default",
            ordered_target_ids=(
                "deterministic-primary",
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
    assert (
        result.decision.status
        is RoutingDecisionStatus.SELECTED
    )
    assert (
        result.execution.executed_target_id
        == "deterministic-primary"
    )

    record = evidence.get(
        "routing-runtime-selected"
    )
    assert record is not None
    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )
    assert (
        record.executed_target_id
        == "deterministic-primary"
    )


def test_factory_composes_no_eligible_evidence_end_to_end() -> None:
    catalog = _catalog(
        enabled=False,
    )
    evidence = InMemoryRoutingEvidenceRepository()

    runtime = build_provider_routing_runtime(
        settings=_settings(),
        catalog=catalog,
        evidence=evidence,
    )

    result = runtime.routing.route_and_execute(
        evidence_id="routing-runtime-not-executed",
        policy=RoutingPolicy(
            policy_id="default",
            ordered_target_ids=(
                "deterministic-primary",
            ),
        ),
        requirement=RoutingRequirement(),
        request=RewriteRequest(
            text="No provider should execute.",
        ),
        observed_at=_observed_at(),
    )

    assert isinstance(
        result,
        ProviderRoutingNotExecutedResult,
    )
    assert (
        result.decision.status
        is RoutingDecisionStatus.NO_ELIGIBLE_TARGET
    )

    record = evidence.get(
        "routing-runtime-not-executed"
    )
    assert record is not None
    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.NOT_EXECUTED
    )
    assert record.executed_target_id is None
    assert record.attempts == ()


def test_factory_preserves_single_catalog_identity() -> None:
    catalog = _catalog()
    evidence = InMemoryRoutingEvidenceRepository()

    runtime = build_provider_routing_runtime(
        settings=_settings(),
        catalog=catalog,
        evidence=evidence,
    )

    assert runtime.catalog is catalog
    assert runtime.decision._catalog is catalog
    assert runtime.execution._catalog is catalog


def test_empty_catalog_fails_composition_explicitly() -> None:
    catalog = InMemoryProviderCatalogRepository()

    with pytest.raises(
        ProviderRoutingRuntimeCompositionError,
        match="requires a provisioned catalog",
    ):
        build_provider_routing_runtime(
            settings=_settings(),
            catalog=catalog,
            evidence=InMemoryRoutingEvidenceRepository(),
        )


def test_catalog_listing_failure_is_wrapped() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.list_targets.side_effect = RuntimeError(
        "database unavailable",
    )

    with pytest.raises(
        ProviderRoutingRuntimeCompositionError,
        match="catalog listing failed",
    ) as captured:
        build_provider_routing_runtime(
            settings=_settings(),
            catalog=catalog,
            evidence=InMemoryRoutingEvidenceRepository(),
        )

    assert isinstance(
        captured.value.__cause__,
        RuntimeError,
    )
