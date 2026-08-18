from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.v2.domain.provider_routing import (
    FallbackPolicy,
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
    RoutingCandidateIneligibilityReason,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
    ProviderCatalogRepository,
)
from app.v2.services.provider_routing_decision_service import (
    ProviderRoutingDecisionService,
    ProviderRoutingResolutionError,
)


def _target(
    *,
    target_id: str,
    enabled: bool = True,
    capabilities: frozenset[
        ProviderCapability
    ] | None = None,
) -> ProviderModelTarget:
    resolved_capabilities = (
        capabilities
        if capabilities is not None
        else frozenset(
            {
                ProviderCapability.REWRITE,
            }
        )
    )

    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id="provider",
            display_name="Provider",
        ),
        model=ModelIdentity(
            provider_id="provider",
            model_id=f"model-{target_id}",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=resolved_capabilities,
        ),
        enabled=enabled,
    )


def _single_policy(
    target_id: str = "primary",
) -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=(target_id,),
    )


def _fallback_policy() -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=(
            "primary",
            "fallback",
        ),
        fallback_policy=FallbackPolicy(
            enabled=True,
            failure_categories=(
                RoutingFailureCategory.TRANSPORT,
            ),
        ),
    )


def _service_with(
    *targets: ProviderModelTarget,
) -> ProviderRoutingDecisionService:
    catalog = InMemoryProviderCatalogRepository()

    for target in targets:
        catalog.create(target)

    return ProviderRoutingDecisionService(
        catalog=catalog,
    )


def test_primary_target_is_selected_when_eligible() -> None:
    service = _service_with(
        _target(target_id="primary")
    )

    decision = service.evaluate(
        policy=_single_policy(),
        requirement=RoutingRequirement(
            required_capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
    )

    assert decision.status is RoutingDecisionStatus.SELECTED
    assert (
        decision.reason
        is RoutingDecisionReason.PRIMARY_SELECTED
    )
    assert decision.selected_target_id == "primary"
    assert len(decision.candidates) == 1
    assert decision.candidates[0].eligible is True


def test_disabled_target_is_ineligible() -> None:
    service = _service_with(
        _target(
            target_id="primary",
            enabled=False,
        )
    )

    decision = service.evaluate(
        policy=_single_policy(),
        requirement=RoutingRequirement(),
    )

    assert (
        decision.status
        is RoutingDecisionStatus.NO_ELIGIBLE_TARGET
    )
    assert decision.candidates[0].ineligibility_reasons == (
        RoutingCandidateIneligibilityReason.TARGET_DISABLED,
    )


def test_missing_capability_is_ineligible() -> None:
    service = _service_with(
        _target(
            target_id="primary",
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        )
    )

    decision = service.evaluate(
        policy=_single_policy(),
        requirement=RoutingRequirement(
            required_capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                    ProviderCapability.CLAIM_LOCK,
                }
            )
        ),
    )

    assert decision.candidates[0].ineligibility_reasons == (
        RoutingCandidateIneligibilityReason.MISSING_CAPABILITY,
    )


def test_explicitly_excluded_target_is_ineligible() -> None:
    service = _service_with(
        _target(target_id="primary")
    )

    decision = service.evaluate(
        policy=_single_policy(),
        requirement=RoutingRequirement(
            excluded_target_ids=("primary",)
        ),
    )

    assert decision.candidates[0].ineligibility_reasons == (
        RoutingCandidateIneligibilityReason.EXCLUDED_BY_REQUIREMENT,
    )


def test_candidate_can_have_multiple_ineligibility_reasons() -> None:
    service = _service_with(
        _target(
            target_id="primary",
            enabled=False,
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        )
    )

    decision = service.evaluate(
        policy=_single_policy(),
        requirement=RoutingRequirement(
            required_capabilities=frozenset(
                {
                    ProviderCapability.CLAIM_LOCK,
                }
            ),
            excluded_target_ids=("primary",),
        ),
    )

    assert decision.candidates[0].ineligibility_reasons == (
        RoutingCandidateIneligibilityReason.TARGET_DISABLED,
        RoutingCandidateIneligibilityReason.MISSING_CAPABILITY,
        RoutingCandidateIneligibilityReason.EXCLUDED_BY_REQUIREMENT,
    )


def test_first_eligible_fallback_target_is_selected() -> None:
    service = _service_with(
        _target(
            target_id="primary",
            enabled=False,
        ),
        _target(
            target_id="fallback",
        ),
    )

    decision = service.evaluate(
        policy=_fallback_policy(),
        requirement=RoutingRequirement(),
    )

    assert decision.status is RoutingDecisionStatus.SELECTED
    assert (
        decision.reason
        is RoutingDecisionReason.FALLBACK_SELECTED
    )
    assert decision.selected_target_id == "fallback"
    assert decision.candidates[0].eligible is False
    assert decision.candidates[1].eligible is True


def test_policy_order_is_preserved_in_candidate_evidence() -> None:
    service = _service_with(
        _target(target_id="primary"),
        _target(target_id="fallback"),
    )

    decision = service.evaluate(
        policy=_fallback_policy(),
        requirement=RoutingRequirement(),
    )

    assert tuple(
        candidate.target_id
        for candidate in decision.candidates
    ) == (
        "primary",
        "fallback",
    )


def test_primary_wins_when_multiple_targets_are_eligible() -> None:
    service = _service_with(
        _target(target_id="primary"),
        _target(target_id="fallback"),
    )

    decision = service.evaluate(
        policy=_fallback_policy(),
        requirement=RoutingRequirement(),
    )

    assert decision.selected_target_id == "primary"
    assert (
        decision.reason
        is RoutingDecisionReason.PRIMARY_SELECTED
    )


def test_no_eligible_target_returns_complete_evidence() -> None:
    service = _service_with(
        _target(
            target_id="primary",
            enabled=False,
        ),
        _target(
            target_id="fallback",
            enabled=False,
        ),
    )

    decision = service.evaluate(
        policy=_fallback_policy(),
        requirement=RoutingRequirement(),
    )

    assert (
        decision.status
        is RoutingDecisionStatus.NO_ELIGIBLE_TARGET
    )
    assert (
        decision.reason
        is RoutingDecisionReason.NO_ELIGIBLE_TARGET
    )
    assert decision.selected_target_id is None
    assert len(decision.candidates) == 2
    assert all(
        not candidate.eligible
        for candidate in decision.candidates
    )


def test_missing_catalog_target_fails_closed() -> None:
    service = _service_with()

    with pytest.raises(
        ProviderRoutingResolutionError,
        match="not present in provider catalog",
    ):
        service.evaluate(
            policy=_single_policy(),
            requirement=RoutingRequirement(),
        )


def test_missing_later_policy_target_also_fails_closed() -> None:
    service = _service_with(
        _target(target_id="primary")
    )

    with pytest.raises(
        ProviderRoutingResolutionError,
        match="fallback",
    ):
        service.evaluate(
            policy=_fallback_policy(),
            requirement=RoutingRequirement(),
        )


def test_catalog_lookup_failure_is_wrapped() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.get.side_effect = RuntimeError(
        "database unavailable"
    )

    service = ProviderRoutingDecisionService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderRoutingResolutionError,
        match="catalog lookup failed",
    ) as exc_info:
        service.evaluate(
            policy=_single_policy(),
            requirement=RoutingRequirement(),
        )

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )


def test_catalog_identity_mismatch_fails_closed() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.get.return_value = _target(
        target_id="different"
    )

    service = ProviderRoutingDecisionService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderRoutingResolutionError,
        match="identity",
    ):
        service.evaluate(
            policy=_single_policy("requested"),
            requirement=RoutingRequirement(),
        )


def test_failure_categories_do_not_change_static_selection() -> None:
    policy = RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=(
            "primary",
            "fallback",
        ),
        fallback_policy=FallbackPolicy(
            enabled=True,
            failure_categories=(
                RoutingFailureCategory.CONFIGURATION,
                RoutingFailureCategory.RESPONSE,
            ),
        ),
    )

    service = _service_with(
        _target(
            target_id="primary",
            enabled=False,
        ),
        _target(target_id="fallback"),
    )

    decision = service.evaluate(
        policy=policy,
        requirement=RoutingRequirement(),
    )

    assert decision.selected_target_id == "fallback"


def test_service_does_not_list_or_mutate_catalog() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.get.return_value = _target(
        target_id="primary"
    )

    service = ProviderRoutingDecisionService(
        catalog=catalog,
    )

    service.evaluate(
        policy=_single_policy(),
        requirement=RoutingRequirement(),
    )

    catalog.get.assert_called_once_with("primary")
    catalog.list_targets.assert_not_called()
    catalog.create.assert_not_called()
