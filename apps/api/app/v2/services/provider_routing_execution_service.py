from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.models import RewriteRequest
from app.providers.base import RewriteProviderResult
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    ProviderModelTarget,
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.services.provider_execution_adapter import (
    ProviderTargetExecutionAdapter,
)


class ProviderExecutionAttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PROVIDER_ERROR = "provider_error"


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderExecutionAttempt:
    target_id: str
    outcome: ProviderExecutionAttemptOutcome
    failure_category: RoutingFailureCategory | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderRoutingExecutionResult:
    provider_result: RewriteProviderResult
    initial_target_id: str
    executed_target_id: str
    execution_fallback_used: bool
    attempts: tuple[ProviderExecutionAttempt, ...]


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderRoutingExecutionFailureResult:
    error: RewriteProviderError
    initial_target_id: str
    attempts: tuple[ProviderExecutionAttempt, ...]


ProviderRoutingExecutionOutcome = (
    ProviderRoutingExecutionResult
    | ProviderRoutingExecutionFailureResult
)


class ProviderRoutingExecutionResolutionError(RuntimeError):
    pass


class ProviderRoutingExecutionService:
    def __init__(
        self,
        *,
        catalog: ProviderCatalogRepository,
        executor: ProviderTargetExecutionAdapter,
    ) -> None:
        self._catalog = catalog
        self._executor = executor

    def execute(
        self,
        *,
        policy: RoutingPolicy,
        decision: RoutingDecision,
        request: RewriteRequest,
    ) -> ProviderRoutingExecutionResult:
        outcome = self.execute_outcome(
            policy=policy,
            decision=decision,
            request=request,
        )

        if isinstance(
            outcome,
            ProviderRoutingExecutionFailureResult,
        ):
            raise outcome.error

        return outcome

    def execute_outcome(
        self,
        *,
        policy: RoutingPolicy,
        decision: RoutingDecision,
        request: RewriteRequest,
    ) -> ProviderRoutingExecutionOutcome:
        selected_index = self._validated_selected_index(
            policy=policy,
            decision=decision,
        )

        execution_target_ids = tuple(
            candidate.target_id
            for candidate in decision.candidates[
                selected_index:
            ]
            if candidate.eligible
        )

        if not execution_target_ids:
            raise ProviderRoutingExecutionResolutionError(
                "routing decision contains no executable target"
            )

        attempts: list[
            ProviderExecutionAttempt
        ] = []

        for index, target_id in enumerate(
            execution_target_ids
        ):
            target = self._resolve_target(
                target_id
            )

            try:
                provider_result = self._executor.execute(
                    target=target,
                    request=request,
                )
            except RewriteProviderError as exc:
                failure_category = (
                    _classify_provider_failure(exc)
                )

                attempts.append(
                    ProviderExecutionAttempt(
                        target_id=target_id,
                        outcome=(
                            ProviderExecutionAttemptOutcome.PROVIDER_ERROR
                        ),
                        failure_category=failure_category,
                    )
                )

                has_later_target = (
                    index + 1
                    < len(execution_target_ids)
                )

                if (
                    not has_later_target
                    or not _fallback_authorized(
                        policy=policy,
                        failure_category=failure_category,
                    )
                ):
                    return ProviderRoutingExecutionFailureResult(
                        error=exc,
                        initial_target_id=execution_target_ids[0],
                        attempts=tuple(attempts),
                    )

                continue

            attempts.append(
                ProviderExecutionAttempt(
                    target_id=target_id,
                    outcome=(
                        ProviderExecutionAttemptOutcome.SUCCEEDED
                    ),
                )
            )

            return ProviderRoutingExecutionResult(
                provider_result=provider_result,
                initial_target_id=execution_target_ids[0],
                executed_target_id=target_id,
                execution_fallback_used=(
                    len(attempts) > 1
                ),
                attempts=tuple(attempts),
            )

        raise ProviderRoutingExecutionResolutionError(
            "provider routing execution ended without "
            "a result or provider failure"
        )

    def _resolve_target(
        self,
        target_id: str,
    ) -> ProviderModelTarget:
        try:
            target = self._catalog.get(
                target_id
            )
        except Exception as exc:
            raise ProviderRoutingExecutionResolutionError(
                "provider routing execution catalog lookup "
                f"failed for target: {target_id}"
            ) from exc

        if target is None:
            raise ProviderRoutingExecutionResolutionError(
                "routing execution target is not present "
                f"in provider catalog: {target_id}"
            )

        if target.target_id != target_id:
            raise ProviderRoutingExecutionResolutionError(
                "provider catalog returned a target identity "
                "different from the requested execution target"
            )

        return target

    @staticmethod
    def _validated_selected_index(
        *,
        policy: RoutingPolicy,
        decision: RoutingDecision,
    ) -> int:
        if decision.policy_id != policy.policy_id:
            raise ProviderRoutingExecutionResolutionError(
                "routing decision policy identity does not "
                "match execution policy"
            )

        candidate_ids = tuple(
            candidate.target_id
            for candidate in decision.candidates
        )

        if (
            candidate_ids
            != policy.ordered_target_ids
        ):
            raise ProviderRoutingExecutionResolutionError(
                "routing decision candidate order does not "
                "match execution policy"
            )

        if (
            decision.status
            is not RoutingDecisionStatus.SELECTED
            or decision.selected_target_id is None
        ):
            raise ProviderRoutingExecutionResolutionError(
                "routing execution requires a selected decision"
            )

        try:
            return candidate_ids.index(
                decision.selected_target_id
            )
        except ValueError as exc:
            raise ProviderRoutingExecutionResolutionError(
                "selected routing target is absent from "
                "decision candidates"
            ) from exc


def _classify_provider_failure(
    error: RewriteProviderError,
) -> RoutingFailureCategory:
    if isinstance(
        error,
        RewriteProviderConfigurationError,
    ):
        return RoutingFailureCategory.CONFIGURATION

    if isinstance(
        error,
        RewriteProviderTransportError,
    ):
        return RoutingFailureCategory.TRANSPORT

    if isinstance(
        error,
        RewriteProviderResponseError,
    ):
        return RoutingFailureCategory.RESPONSE

    return RoutingFailureCategory.PROVIDER


def _fallback_authorized(
    *,
    policy: RoutingPolicy,
    failure_category: RoutingFailureCategory,
) -> bool:
    return (
        policy.fallback_policy.enabled
        and failure_category
        in policy.fallback_policy.failure_categories
    )
