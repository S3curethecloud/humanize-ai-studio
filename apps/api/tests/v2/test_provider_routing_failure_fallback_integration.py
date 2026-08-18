from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from app.domain.models import RewriteRequest
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
    RoutingCandidateIneligibilityReason,
    RoutingFailureCategory,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceAttemptOutcome,
    RoutingEvidenceExecutionOutcome,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.governed_provider_routing_execution_service import (
    GovernedProviderRoutingExecutionService,
)
from app.v2.services.governed_provider_routing_service import (
    GovernedProviderRoutingService,
    ProviderRoutingSelectedResult,
)
from app.v2.services.provider_execution_adapter import (
    ProviderExecutionIntegrityError,
)
from app.v2.services.provider_routing_decision_service import (
    ProviderRoutingDecisionService,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderRoutingExecutionService,
)
from app.v2.services.routing_decision_evidence_service import (
    RoutingDecisionEvidenceService,
)
from app.v2.services.routing_execution_evidence_service import (
    RoutingExecutionEvidenceService,
)


def _target(
    *,
    target_id: str,
    enabled: bool = True,
) -> ProviderModelTarget:
    provider_id = f"provider-{target_id}"

    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name=f"Provider {target_id}",
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=f"model-{target_id}",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=enabled,
    )


def _result(
    target: ProviderModelTarget,
) -> RewriteProviderResult:
    return RewriteProviderResult(
        text=f"Result from {target.target_id}.",
        changes=[],
        provider_name=target.provider.provider_id,
        model_name=target.model.model_id,
        prompt_version="v2-8-i3",
        latency_ms=1.0,
        primary_provider_name=(
            target.provider.provider_id
        ),
        fallback_used=False,
        provider_error_category=None,
        usage=ProviderUsage(),
    )


@dataclass
class ScriptedExecutor:
    outcomes: dict[
        str,
        RewriteProviderResult | Exception,
    ]
    calls: list[str] = field(
        default_factory=list
    )

    def execute(
        self,
        *,
        target: ProviderModelTarget,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        del request

        self.calls.append(
            target.target_id
        )

        outcome = self.outcomes[
            target.target_id
        ]

        if isinstance(
            outcome,
            Exception,
        ):
            raise outcome

        return outcome


def _runtime(
    *,
    targets: tuple[
        ProviderModelTarget,
        ...,
    ],
    executor: ScriptedExecutor,
) -> tuple[
    GovernedProviderRoutingService,
    InMemoryRoutingEvidenceRepository,
]:
    catalog = InMemoryProviderCatalogRepository()

    for target in targets:
        catalog.create(target)

    repository = (
        InMemoryRoutingEvidenceRepository()
    )

    execution = ProviderRoutingExecutionService(
        catalog=catalog,
        executor=executor,
    )

    governed_execution = (
        GovernedProviderRoutingExecutionService(
            execution=execution,
            evidence=RoutingExecutionEvidenceService(
                repository=repository,
            ),
        )
    )

    routing = GovernedProviderRoutingService(
        decision=ProviderRoutingDecisionService(
            catalog=catalog,
        ),
        execution=governed_execution,
        non_execution_evidence=(
            RoutingDecisionEvidenceService(
                repository=repository,
            )
        ),
    )

    return routing, repository


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="V2.8I3 governed routing test.",
    )


def _observed_at(
    minute: int,
) -> datetime:
    return datetime(
        2026,
        8,
        18,
        6,
        minute,
        tzinfo=UTC,
    )


def _policy(
    *target_ids: str,
    categories: tuple[
        RoutingFailureCategory,
        ...,
    ],
) -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="v2-8-i3-policy",
        ordered_target_ids=target_ids,
        fallback_policy=FallbackPolicy(
            enabled=True,
            failure_categories=categories,
        ),
    )


def _requirement() -> RoutingRequirement:
    return RoutingRequirement(
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        )
    )


def test_authorized_provider_failure_falls_back_and_persists_attempts(
) -> None:
    primary = _target(
        target_id="primary"
    )
    fallback = _target(
        target_id="fallback"
    )

    executor = ScriptedExecutor(
        outcomes={
            "primary": (
                RewriteProviderTransportError(
                    "primary unavailable"
                )
            ),
            "fallback": _result(
                fallback
            ),
        }
    )

    routing, repository = _runtime(
        targets=(
            primary,
            fallback,
        ),
        executor=executor,
    )

    result = routing.route_and_execute(
        evidence_id="i3-authorized",
        policy=_policy(
            "primary",
            "fallback",
            categories=(
                RoutingFailureCategory.TRANSPORT,
            ),
        ),
        requirement=_requirement(),
        request=_request(),
        observed_at=_observed_at(1),
    )

    assert isinstance(
        result,
        ProviderRoutingSelectedResult,
    )
    assert executor.calls == [
        "primary",
        "fallback",
    ]
    assert (
        result.execution.initial_target_id
        == "primary"
    )
    assert (
        result.execution.executed_target_id
        == "fallback"
    )
    assert (
        result.execution.execution_fallback_used
        is True
    )

    record = repository.get(
        "i3-authorized"
    )

    assert record is not None
    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )
    assert (
        record.executed_target_id
        == "fallback"
    )
    assert (
        record.execution_fallback_used
        is True
    )
    assert tuple(
        attempt.target_id
        for attempt in record.attempts
    ) == (
        "primary",
        "fallback",
    )
    assert (
        record.attempts[0].outcome
        is RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
    )
    assert (
        record.attempts[0].failure_category
        is RoutingFailureCategory.TRANSPORT
    )
    assert (
        record.attempts[1].outcome
        is RoutingEvidenceAttemptOutcome.SUCCEEDED
    )


def test_unauthorized_provider_failure_does_not_fallback_and_is_evidenced(
) -> None:
    primary = _target(
        target_id="primary"
    )
    fallback = _target(
        target_id="fallback"
    )

    error = RewriteProviderResponseError(
        "invalid provider response"
    )

    executor = ScriptedExecutor(
        outcomes={
            "primary": error,
            "fallback": _result(
                fallback
            ),
        }
    )

    routing, repository = _runtime(
        targets=(
            primary,
            fallback,
        ),
        executor=executor,
    )

    with pytest.raises(
        RewriteProviderResponseError,
    ) as exc_info:
        routing.route_and_execute(
            evidence_id="i3-unauthorized",
            policy=_policy(
                "primary",
                "fallback",
                categories=(
                    RoutingFailureCategory.TRANSPORT,
                ),
            ),
            requirement=_requirement(),
            request=_request(),
            observed_at=_observed_at(2),
        )

    assert exc_info.value is error
    assert executor.calls == [
        "primary",
    ]

    record = repository.get(
        "i3-unauthorized"
    )

    assert record is not None
    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.FAILED
    )
    assert (
        record.executed_target_id
        is None
    )
    assert (
        record.execution_fallback_used
        is False
    )
    assert len(record.attempts) == 1
    assert (
        record.attempts[0].failure_category
        is RoutingFailureCategory.RESPONSE
    )


def test_non_provider_integrity_failure_never_falls_back_or_fabricates_evidence(
) -> None:
    primary = _target(
        target_id="primary"
    )
    fallback = _target(
        target_id="fallback"
    )

    error = ProviderExecutionIntegrityError(
        "execution identity mismatch"
    )

    executor = ScriptedExecutor(
        outcomes={
            "primary": error,
            "fallback": _result(
                fallback
            ),
        }
    )

    routing, repository = _runtime(
        targets=(
            primary,
            fallback,
        ),
        executor=executor,
    )

    with pytest.raises(
        ProviderExecutionIntegrityError,
    ) as exc_info:
        routing.route_and_execute(
            evidence_id="i3-integrity",
            policy=_policy(
                "primary",
                "fallback",
                categories=(
                    RoutingFailureCategory.CONFIGURATION,
                    RoutingFailureCategory.TRANSPORT,
                    RoutingFailureCategory.RESPONSE,
                    RoutingFailureCategory.PROVIDER,
                ),
            ),
            requirement=_requirement(),
            request=_request(),
            observed_at=_observed_at(3),
        )

    assert exc_info.value is error
    assert executor.calls == [
        "primary",
    ]
    assert (
        repository.get(
            "i3-integrity"
        )
        is None
    )


def test_ineligible_intermediate_target_is_skipped_during_authorized_fallback(
) -> None:
    primary = _target(
        target_id="primary"
    )
    disabled = _target(
        target_id="disabled",
        enabled=False,
    )
    final = _target(
        target_id="final"
    )

    executor = ScriptedExecutor(
        outcomes={
            "primary": (
                RewriteProviderTransportError(
                    "primary unavailable"
                )
            ),
            "disabled": _result(
                disabled
            ),
            "final": _result(
                final
            ),
        }
    )

    routing, repository = _runtime(
        targets=(
            primary,
            disabled,
            final,
        ),
        executor=executor,
    )

    result = routing.route_and_execute(
        evidence_id="i3-skip-disabled",
        policy=_policy(
            "primary",
            "disabled",
            "final",
            categories=(
                RoutingFailureCategory.TRANSPORT,
            ),
        ),
        requirement=_requirement(),
        request=_request(),
        observed_at=_observed_at(4),
    )

    assert isinstance(
        result,
        ProviderRoutingSelectedResult,
    )

    assert executor.calls == [
        "primary",
        "final",
    ]

    assert (
        result.decision.candidates[1].target_id
        == "disabled"
    )
    assert (
        result.decision.candidates[1].eligible
        is False
    )
    assert (
        RoutingCandidateIneligibilityReason.TARGET_DISABLED
        in (
            result.decision
            .candidates[1]
            .ineligibility_reasons
        )
    )

    assert (
        result.execution.executed_target_id
        == "final"
    )
    assert (
        result.execution.execution_fallback_used
        is True
    )

    record = repository.get(
        "i3-skip-disabled"
    )

    assert record is not None
    assert tuple(
        attempt.target_id
        for attempt in record.attempts
    ) == (
        "primary",
        "final",
    )
