from __future__ import annotations

from app.v2.domain.provider_routing import (
    ProviderModelTarget,
    RoutingCandidate,
    RoutingCandidateIneligibilityReason,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)


class ProviderRoutingResolutionError(RuntimeError):
    pass


class ProviderRoutingDecisionService:
    def __init__(
        self,
        *,
        catalog: ProviderCatalogRepository,
    ) -> None:
        self._catalog = catalog

    def evaluate(
        self,
        *,
        policy: RoutingPolicy,
        requirement: RoutingRequirement,
    ) -> RoutingDecision:
        candidates = tuple(
            self._evaluate_target(
                target_id=target_id,
                requirement=requirement,
            )
            for target_id in policy.ordered_target_ids
        )

        selected_index = next(
            (
                index
                for index, candidate in enumerate(candidates)
                if candidate.eligible
            ),
            None,
        )

        if selected_index is None:
            return RoutingDecision(
                policy_id=policy.policy_id,
                status=(
                    RoutingDecisionStatus.NO_ELIGIBLE_TARGET
                ),
                reason=(
                    RoutingDecisionReason.NO_ELIGIBLE_TARGET
                ),
                candidates=candidates,
            )

        selected = candidates[selected_index]

        reason = (
            RoutingDecisionReason.PRIMARY_SELECTED
            if selected_index == 0
            else RoutingDecisionReason.FALLBACK_SELECTED
        )

        return RoutingDecision(
            policy_id=policy.policy_id,
            status=RoutingDecisionStatus.SELECTED,
            reason=reason,
            selected_target_id=selected.target_id,
            candidates=candidates,
        )

    def _evaluate_target(
        self,
        *,
        target_id: str,
        requirement: RoutingRequirement,
    ) -> RoutingCandidate:
        target = self._resolve_target(target_id)

        reasons = self._ineligibility_reasons(
            target=target,
            requirement=requirement,
        )

        return RoutingCandidate(
            target_id=target.target_id,
            eligible=not reasons,
            ineligibility_reasons=reasons,
        )

    def _resolve_target(
        self,
        target_id: str,
    ) -> ProviderModelTarget:
        try:
            target = self._catalog.get(target_id)
        except Exception as exc:
            raise ProviderRoutingResolutionError(
                "provider routing catalog lookup failed "
                f"for target: {target_id}"
            ) from exc

        if target is None:
            raise ProviderRoutingResolutionError(
                "routing policy target is not present "
                f"in provider catalog: {target_id}"
            )

        if target.target_id != target_id:
            raise ProviderRoutingResolutionError(
                "provider catalog returned a target identity "
                "different from the requested routing target"
            )

        return target

    @staticmethod
    def _ineligibility_reasons(
        *,
        target: ProviderModelTarget,
        requirement: RoutingRequirement,
    ) -> tuple[
        RoutingCandidateIneligibilityReason,
        ...,
    ]:
        reasons: list[
            RoutingCandidateIneligibilityReason
        ] = []

        if not target.enabled:
            reasons.append(
                RoutingCandidateIneligibilityReason.TARGET_DISABLED
            )

        if not requirement.required_capabilities.issubset(
            target.capabilities.capabilities
        ):
            reasons.append(
                RoutingCandidateIneligibilityReason.MISSING_CAPABILITY
            )

        if target.target_id in requirement.excluded_target_ids:
            reasons.append(
                RoutingCandidateIneligibilityReason.EXCLUDED_BY_REQUIREMENT
            )

        return tuple(reasons)
