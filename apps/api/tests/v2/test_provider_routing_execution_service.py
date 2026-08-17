from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.domain.models import (
    RewriteIntensity,
    RewriteRequest,
)
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderError,
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
    RoutingCandidate,
    RoutingCandidateIneligibilityReason,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
    ProviderCatalogRepository,
)
from app.v2.services.provider_execution_adapter import (
    ProviderExecutionBindingError,
    ProviderExecutionIntegrityError,
    ProviderTargetExecutionAdapter,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionResolutionError,
    ProviderRoutingExecutionService,
)


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="The original text.",
        audience="general",
        tone="professional",
        intensity=RewriteIntensity.NATURAL_REWRITE,
    )


def _target(
    target_id: str,
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=f"provider-{target_id}",
            display_name=f"Provider {target_id}",
        ),
        model=ModelIdentity(
            provider_id=f"provider-{target_id}",
            model_id=f"model-{target_id}",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
    )


def _result(
    target_id: str,
) -> RewriteProviderResult:
    return RewriteProviderResult(
        text=f"Result from {target_id}.",
        changes=[],
        provider_name=f"provider-{target_id}",
        model_name=f"model-{target_id}",
        prompt_version="prompt-v1",
        latency_ms=1.0,
        primary_provider_name=f"provider-{target_id}",
        fallback_used=False,
        provider_error_category=None,
        usage=ProviderUsage(),
    )


def _policy(
    *target_ids: str,
    categories: tuple[
        RoutingFailureCategory,
        ...,
    ] = (
        RoutingFailureCategory.TRANSPORT,
    ),
) -> RoutingPolicy:
    if len(target_ids) == 1:
        return RoutingPolicy(
            policy_id="policy",
            ordered_target_ids=target_ids,
        )

    return RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=target_ids,
        fallback_policy=FallbackPolicy(
            enabled=True,
            failure_categories=categories,
        ),
    )


def _decision(
    *,
    candidates: tuple[
        RoutingCandidate,
        ...,
    ],
    selected_target_id: str,
) -> RoutingDecision:
    selected_index = tuple(
        candidate.target_id
        for candidate in candidates
    ).index(selected_target_id)

    return RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=(
            RoutingDecisionReason.PRIMARY_SELECTED
            if selected_index == 0
            else RoutingDecisionReason.FALLBACK_SELECTED
        ),
        selected_target_id=selected_target_id,
        candidates=candidates,
    )


def _eligible(
    target_id: str,
) -> RoutingCandidate:
    return RoutingCandidate(
        target_id=target_id,
        eligible=True,
    )


def _disabled(
    target_id: str,
) -> RoutingCandidate:
    return RoutingCandidate(
        target_id=target_id,
        eligible=False,
        ineligibility_reasons=(
            RoutingCandidateIneligibilityReason.TARGET_DISABLED,
        ),
    )


def _catalog(
    *target_ids: str,
) -> InMemoryProviderCatalogRepository:
    catalog = InMemoryProviderCatalogRepository()

    for target_id in target_ids:
        catalog.create(
            _target(target_id)
        )

    return catalog


def _executor() -> MagicMock:
    return MagicMock(
        spec=ProviderTargetExecutionAdapter,
    )


def test_executes_selected_primary_target() -> None:
    executor = _executor()
    executor.execute.return_value = _result(
        "primary"
    )

    service = ProviderRoutingExecutionService(
        catalog=_catalog("primary"),
        executor=executor,
    )

    result = service.execute(
        policy=_policy("primary"),
        decision=_decision(
            candidates=(
                _eligible("primary"),
            ),
            selected_target_id="primary",
        ),
        request=_request(),
    )

    assert result.executed_target_id == "primary"
    assert result.initial_target_id == "primary"
    assert result.execution_fallback_used is False
    assert len(result.attempts) == 1
    assert (
        result.attempts[0].outcome
        is ProviderExecutionAttemptOutcome.SUCCEEDED
    )


def test_statically_selected_secondary_is_not_execution_fallback() -> None:
    executor = _executor()
    executor.execute.return_value = _result(
        "secondary"
    )

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "secondary",
        ),
        executor=executor,
    )

    result = service.execute(
        policy=_policy(
            "primary",
            "secondary",
        ),
        decision=_decision(
            candidates=(
                _disabled("primary"),
                _eligible("secondary"),
            ),
            selected_target_id="secondary",
        ),
        request=_request(),
    )

    assert result.initial_target_id == "secondary"
    assert result.executed_target_id == "secondary"
    assert result.execution_fallback_used is False
    assert len(result.attempts) == 1


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (
            RewriteProviderConfigurationError(
                "configuration"
            ),
            RoutingFailureCategory.CONFIGURATION,
        ),
        (
            RewriteProviderTransportError(
                "transport"
            ),
            RoutingFailureCategory.TRANSPORT,
        ),
        (
            RewriteProviderResponseError(
                "response"
            ),
            RoutingFailureCategory.RESPONSE,
        ),
        (
            RewriteProviderError(
                "provider"
            ),
            RoutingFailureCategory.PROVIDER,
        ),
    ],
)
def test_authorized_provider_failure_advances_to_fallback(
    error: RewriteProviderError,
    category: RoutingFailureCategory,
) -> None:
    executor = _executor()
    executor.execute.side_effect = [
        error,
        _result("fallback"),
    ]

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "fallback",
        ),
        executor=executor,
    )

    result = service.execute(
        policy=_policy(
            "primary",
            "fallback",
            categories=(category,),
        ),
        decision=_decision(
            candidates=(
                _eligible("primary"),
                _eligible("fallback"),
            ),
            selected_target_id="primary",
        ),
        request=_request(),
    )

    assert result.execution_fallback_used is True
    assert result.executed_target_id == "fallback"
    assert result.attempts[0].failure_category is category
    assert (
        result.attempts[0].outcome
        is ProviderExecutionAttemptOutcome.PROVIDER_ERROR
    )
    assert (
        result.attempts[1].outcome
        is ProviderExecutionAttemptOutcome.SUCCEEDED
    )


def test_forbidden_failure_category_does_not_fallback() -> None:
    executor = _executor()
    error = RewriteProviderResponseError(
        "response"
    )
    executor.execute.side_effect = error

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "fallback",
        ),
        executor=executor,
    )

    with pytest.raises(
        RewriteProviderResponseError,
    ) as exc_info:
        service.execute(
            policy=_policy(
                "primary",
                "fallback",
                categories=(
                    RoutingFailureCategory.TRANSPORT,
                ),
            ),
            decision=_decision(
                candidates=(
                    _eligible("primary"),
                    _eligible("fallback"),
                ),
                selected_target_id="primary",
            ),
            request=_request(),
        )

    assert exc_info.value is error
    assert executor.execute.call_count == 1


def test_ineligible_candidate_is_skipped_during_fallback() -> None:
    executor = _executor()
    executor.execute.side_effect = [
        RewriteProviderTransportError(
            "primary failed"
        ),
        _result("third"),
    ]

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "disabled",
            "third",
        ),
        executor=executor,
    )

    result = service.execute(
        policy=_policy(
            "primary",
            "disabled",
            "third",
        ),
        decision=_decision(
            candidates=(
                _eligible("primary"),
                _disabled("disabled"),
                _eligible("third"),
            ),
            selected_target_id="primary",
        ),
        request=_request(),
    )

    assert result.executed_target_id == "third"

    executed_ids = tuple(
        call.kwargs["target"].target_id
        for call in executor.execute.call_args_list
    )

    assert executed_ids == (
        "primary",
        "third",
    )


def test_multiple_authorized_failures_advance_in_order() -> None:
    executor = _executor()
    executor.execute.side_effect = [
        RewriteProviderTransportError("one"),
        RewriteProviderTransportError("two"),
        _result("third"),
    ]

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "second",
            "third",
        ),
        executor=executor,
    )

    result = service.execute(
        policy=_policy(
            "primary",
            "second",
            "third",
        ),
        decision=_decision(
            candidates=(
                _eligible("primary"),
                _eligible("second"),
                _eligible("third"),
            ),
            selected_target_id="primary",
        ),
        request=_request(),
    )

    assert tuple(
        attempt.target_id
        for attempt in result.attempts
    ) == (
        "primary",
        "second",
        "third",
    )

    assert result.executed_target_id == "third"
    assert result.execution_fallback_used is True


def test_final_provider_failure_propagates_unchanged() -> None:
    executor = _executor()

    first = RewriteProviderTransportError(
        "first"
    )
    final = RewriteProviderTransportError(
        "final"
    )

    executor.execute.side_effect = [
        first,
        final,
    ]

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "fallback",
        ),
        executor=executor,
    )

    with pytest.raises(
        RewriteProviderTransportError,
    ) as exc_info:
        service.execute(
            policy=_policy(
                "primary",
                "fallback",
            ),
            decision=_decision(
                candidates=(
                    _eligible("primary"),
                    _eligible("fallback"),
                ),
                selected_target_id="primary",
            ),
            request=_request(),
        )

    assert exc_info.value is final
    assert executor.execute.call_count == 2


@pytest.mark.parametrize(
    "error",
    [
        ProviderExecutionBindingError(
            "binding"
        ),
        ProviderExecutionIntegrityError(
            "integrity"
        ),
        RuntimeError(
            "unexpected"
        ),
    ],
)
def test_non_provider_failure_never_authorizes_fallback(
    error: RuntimeError,
) -> None:
    executor = _executor()
    executor.execute.side_effect = error

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "fallback",
        ),
        executor=executor,
    )

    with pytest.raises(
        type(error),
    ) as exc_info:
        service.execute(
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
            decision=_decision(
                candidates=(
                    _eligible("primary"),
                    _eligible("fallback"),
                ),
                selected_target_id="primary",
            ),
            request=_request(),
        )

    assert exc_info.value is error
    assert executor.execute.call_count == 1


def test_policy_identity_mismatch_fails_closed() -> None:
    executor = _executor()

    decision = RoutingDecision(
        policy_id="other-policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="primary",
        candidates=(
            _eligible("primary"),
        ),
    )

    service = ProviderRoutingExecutionService(
        catalog=_catalog("primary"),
        executor=executor,
    )

    with pytest.raises(
        ProviderRoutingExecutionResolutionError,
        match="policy identity",
    ):
        service.execute(
            policy=_policy("primary"),
            decision=decision,
            request=_request(),
        )

    executor.execute.assert_not_called()


def test_candidate_order_mismatch_fails_closed() -> None:
    executor = _executor()

    decision = _decision(
        candidates=(
            _eligible("fallback"),
            _eligible("primary"),
        ),
        selected_target_id="fallback",
    )

    service = ProviderRoutingExecutionService(
        catalog=_catalog(
            "primary",
            "fallback",
        ),
        executor=executor,
    )

    with pytest.raises(
        ProviderRoutingExecutionResolutionError,
        match="candidate order",
    ):
        service.execute(
            policy=_policy(
                "primary",
                "fallback",
            ),
            decision=decision,
            request=_request(),
        )

    executor.execute.assert_not_called()


def test_no_eligible_decision_cannot_execute() -> None:
    executor = _executor()

    decision = RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.NO_ELIGIBLE_TARGET,
        reason=RoutingDecisionReason.NO_ELIGIBLE_TARGET,
        candidates=(
            _disabled("primary"),
        ),
    )

    service = ProviderRoutingExecutionService(
        catalog=_catalog("primary"),
        executor=executor,
    )

    with pytest.raises(
        ProviderRoutingExecutionResolutionError,
        match="selected decision",
    ):
        service.execute(
            policy=_policy("primary"),
            decision=decision,
            request=_request(),
        )

    executor.execute.assert_not_called()


def test_missing_catalog_target_fails_closed() -> None:
    executor = _executor()

    service = ProviderRoutingExecutionService(
        catalog=_catalog(),
        executor=executor,
    )

    with pytest.raises(
        ProviderRoutingExecutionResolutionError,
        match="not present in provider catalog",
    ):
        service.execute(
            policy=_policy("primary"),
            decision=_decision(
                candidates=(
                    _eligible("primary"),
                ),
                selected_target_id="primary",
            ),
            request=_request(),
        )

    executor.execute.assert_not_called()


def test_catalog_lookup_failure_is_wrapped() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.get.side_effect = RuntimeError(
        "catalog unavailable"
    )

    executor = _executor()

    service = ProviderRoutingExecutionService(
        catalog=catalog,
        executor=executor,
    )

    with pytest.raises(
        ProviderRoutingExecutionResolutionError,
        match="catalog lookup failed",
    ) as exc_info:
        service.execute(
            policy=_policy("primary"),
            decision=_decision(
                candidates=(
                    _eligible("primary"),
                ),
                selected_target_id="primary",
            ),
            request=_request(),
        )

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )
    executor.execute.assert_not_called()


def test_catalog_identity_mismatch_fails_closed() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.get.return_value = _target(
        "different"
    )

    executor = _executor()

    service = ProviderRoutingExecutionService(
        catalog=catalog,
        executor=executor,
    )

    with pytest.raises(
        ProviderRoutingExecutionResolutionError,
        match="target identity",
    ):
        service.execute(
            policy=_policy("primary"),
            decision=_decision(
                candidates=(
                    _eligible("primary"),
                ),
                selected_target_id="primary",
            ),
            request=_request(),
        )

    executor.execute.assert_not_called()
