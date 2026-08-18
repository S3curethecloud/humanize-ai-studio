from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.domain.provider_routing import (
    FallbackPolicy,
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
    RoutingCandidate,
    RoutingCandidateIneligibilityReason,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
    RoutingRequirement,
)


def _provider(
    provider_id: str = "cloudflare",
) -> ProviderIdentity:
    return ProviderIdentity(
        provider_id=provider_id,
        display_name="Cloudflare Workers AI",
    )


def _model(
    provider_id: str = "cloudflare",
) -> ModelIdentity:
    return ModelIdentity(
        provider_id=provider_id,
        model_id="@cf/example/model",
    )


def _capabilities() -> ProviderModelCapabilities:
    return ProviderModelCapabilities(
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        )
    )


def _target() -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id="cloudflare-primary",
        provider=_provider(),
        model=_model(),
        capabilities=_capabilities(),
    )


def _eligible(
    target_id: str,
) -> RoutingCandidate:
    return RoutingCandidate(
        target_id=target_id,
        eligible=True,
    )


def _ineligible(
    target_id: str,
) -> RoutingCandidate:
    return RoutingCandidate(
        target_id=target_id,
        eligible=False,
        ineligibility_reasons=(
            RoutingCandidateIneligibilityReason.MISSING_CAPABILITY,
        ),
    )


def test_provider_model_target_accepts_matching_identity() -> None:
    target = _target()

    assert target.provider.provider_id == "cloudflare"
    assert target.model.provider_id == "cloudflare"
    assert target.enabled is True


def test_provider_model_target_rejects_mismatched_provider() -> None:
    with pytest.raises(
        ValidationError,
        match="provider identities must match",
    ):
        ProviderModelTarget(
            target_id="target",
            provider=_provider("cloudflare"),
            model=_model("other"),
            capabilities=_capabilities(),
        )


def test_capabilities_require_at_least_one_capability() -> None:
    with pytest.raises(ValidationError):
        ProviderModelCapabilities(
            capabilities=frozenset()
        )


def test_disabled_fallback_rejects_failure_categories() -> None:
    with pytest.raises(
        ValidationError,
        match="disabled fallback policy",
    ):
        FallbackPolicy(
            enabled=False,
            failure_categories=(
                RoutingFailureCategory.TRANSPORT,
            ),
        )


def test_enabled_fallback_requires_failure_categories() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failure categories",
    ):
        FallbackPolicy(enabled=True)


def test_enabled_fallback_accepts_explicit_categories() -> None:
    policy = FallbackPolicy(
        enabled=True,
        failure_categories=(
            RoutingFailureCategory.TRANSPORT,
            RoutingFailureCategory.RESPONSE,
        ),
    )

    assert policy.enabled is True


def test_routing_requirement_rejects_duplicate_exclusions() -> None:
    with pytest.raises(
        ValidationError,
        match="excluded target IDs must be unique",
    ):
        RoutingRequirement(
            excluded_target_ids=(
                "target-a",
                "target-a",
            )
        )


def test_single_target_policy_can_disable_fallback() -> None:
    policy = RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=("target-a",),
    )

    assert policy.fallback_policy.enabled is False


def test_multi_target_policy_requires_explicit_fallback() -> None:
    with pytest.raises(
        ValidationError,
        match="requires fallback to be enabled",
    ):
        RoutingPolicy(
            policy_id="policy",
            ordered_target_ids=(
                "target-a",
                "target-b",
            ),
        )


def test_policy_rejects_duplicate_target_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="target IDs must be unique",
    ):
        RoutingPolicy(
            policy_id="policy",
            ordered_target_ids=(
                "target-a",
                "target-a",
            ),
            fallback_policy=FallbackPolicy(
                enabled=True,
                failure_categories=(
                    RoutingFailureCategory.TRANSPORT,
                ),
            ),
        )


def test_eligible_candidate_cannot_have_reasons() -> None:
    with pytest.raises(
        ValidationError,
        match="eligible routing candidate cannot",
    ):
        RoutingCandidate(
            target_id="target",
            eligible=True,
            ineligibility_reasons=(
                RoutingCandidateIneligibilityReason.TARGET_DISABLED,
            ),
        )


def test_ineligible_candidate_requires_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires at least one reason",
    ):
        RoutingCandidate(
            target_id="target",
            eligible=False,
        )


def test_primary_selection_requires_first_candidate() -> None:
    decision = RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="primary",
        candidates=(
            _eligible("primary"),
            _eligible("fallback"),
        ),
    )

    assert decision.selected_target_id == "primary"


def test_fallback_selection_allows_first_candidate_ineligible() -> None:
    decision = RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.FALLBACK_SELECTED,
        selected_target_id="fallback",
        candidates=(
            _ineligible("primary"),
            _eligible("fallback"),
        ),
    )

    assert decision.reason is RoutingDecisionReason.FALLBACK_SELECTED


def test_selection_rejects_non_first_eligible_target() -> None:
    with pytest.raises(
        ValidationError,
        match="first eligible routing candidate",
    ):
        RoutingDecision(
            policy_id="policy",
            status=RoutingDecisionStatus.SELECTED,
            reason=RoutingDecisionReason.FALLBACK_SELECTED,
            selected_target_id="second",
            candidates=(
                _eligible("first"),
                _eligible("second"),
            ),
        )


def test_selection_reason_must_match_candidate_position() -> None:
    with pytest.raises(
        ValidationError,
        match="reason does not match",
    ):
        RoutingDecision(
            policy_id="policy",
            status=RoutingDecisionStatus.SELECTED,
            reason=RoutingDecisionReason.PRIMARY_SELECTED,
            selected_target_id="fallback",
            candidates=(
                _ineligible("primary"),
                _eligible("fallback"),
            ),
        )


def test_no_eligible_target_requires_all_candidates_ineligible() -> None:
    decision = RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.NO_ELIGIBLE_TARGET,
        reason=RoutingDecisionReason.NO_ELIGIBLE_TARGET,
        candidates=(
            _ineligible("primary"),
            _ineligible("fallback"),
        ),
    )

    assert decision.selected_target_id is None


def test_no_eligible_target_rejects_eligible_candidate() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain eligible candidates",
    ):
        RoutingDecision(
            policy_id="policy",
            status=RoutingDecisionStatus.NO_ELIGIBLE_TARGET,
            reason=RoutingDecisionReason.NO_ELIGIBLE_TARGET,
            candidates=(
                _eligible("primary"),
            ),
        )


def test_routing_decision_rejects_duplicate_candidates() -> None:
    with pytest.raises(
        ValidationError,
        match="candidate IDs must be unique",
    ):
        RoutingDecision(
            policy_id="policy",
            status=RoutingDecisionStatus.NO_ELIGIBLE_TARGET,
            reason=RoutingDecisionReason.NO_ELIGIBLE_TARGET,
            candidates=(
                _ineligible("target"),
                _ineligible("target"),
            ),
        )


def test_domain_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderIdentity(
            provider_id="provider",
            display_name="Provider",
            unexpected=True,
        )
