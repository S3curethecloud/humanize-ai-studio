from datetime import (
    UTC,
    datetime,
)
from types import SimpleNamespace

import pytest

from app.domain.models import RewriteRequest
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    ProviderCapability,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.services.enterprise_routing_aware_provider import (
    EnterpriseProviderRoutingNoEligibleTargetError,
    EnterpriseProviderRoutingProviderContext,
    EnterpriseRoutingAwareRewriteProvider,
)
from app.v2.services.governed_provider_routing_service import (
    ProviderRoutingNotExecutedResult,
    ProviderRoutingSelectedResult,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttempt,
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionResult,
)


def rewrite_request() -> RewriteRequest:
    return RewriteRequest(
        text="Original text.",
    )


NOW = datetime(
    2026,
    9,
    2,
    20,
    0,
    tzinfo=UTC,
)


class _LegacyProvider:
    provider_name = "legacy"

    def __init__(
        self,
    ) -> None:
        self.calls = 0

    def rewrite(
        self,
        request,
    ) -> RewriteProviderResult:
        self.calls += 1

        return _provider_result(
            provider_name="legacy",
            model_name="legacy-model",
            text=request.text,
        )


class _Operations:
    def __init__(
        self,
    ) -> None:
        self.reserved: list[
            tuple[str, str]
        ] = []
        self.confirmed: list[
            tuple[str, str]
        ] = []

    def reserve_routing_evidence(
        self,
        *,
        operation_id: str,
        evidence_id: str,
    ):
        self.reserved.append(
            (
                operation_id,
                evidence_id,
            )
        )

    def confirm_routing_evidence(
        self,
        *,
        operation_id: str,
        evidence_id: str,
    ):
        self.confirmed.append(
            (
                operation_id,
                evidence_id,
            )
        )


class _Routing:
    def __init__(
        self,
        *,
        result=None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[
            dict[str, object]
        ] = []

    def route_and_execute(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        if self.error is not None:
            raise self.error

        return self.result


class _Catalog:
    def __init__(
        self,
    ) -> None:
        self.targets = {
            "target-1": SimpleNamespace(
                target_id="target-1",
                provider=SimpleNamespace(
                    provider_id="provider-1",
                ),
            ),
            "target-2": SimpleNamespace(
                target_id="target-2",
                provider=SimpleNamespace(
                    provider_id="provider-2",
                ),
            ),
        }

    def get(
        self,
        target_id: str,
    ):
        return self.targets.get(
            target_id
        )


def _provider_result(
    *,
    provider_name: str,
    model_name: str,
    text: str = "rewritten",
) -> RewriteProviderResult:
    return RewriteProviderResult(
        text=text,
        changes=[],
        provider_name=provider_name,
        model_name=model_name,
        prompt_version="prompt-v1",
        latency_ms=5.0,
        usage=ProviderUsage(
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
        ),
    )


def _policy(
    *,
    fallback: bool = False,
) -> RoutingPolicy:
    if fallback:
        return RoutingPolicy(
            policy_id="policy-1",
            ordered_target_ids=(
                "target-1",
                "target-2",
            ),
            fallback_policy=FallbackPolicy(
                enabled=True,
                failure_categories=(
                    RoutingFailureCategory.TRANSPORT,
                ),
            ),
        )

    return RoutingPolicy(
        policy_id="policy-1",
        ordered_target_ids=(
            "target-1",
        ),
    )


def _context(
    *,
    fallback: bool = False,
) -> EnterpriseProviderRoutingProviderContext:
    return (
        EnterpriseProviderRoutingProviderContext(
            operation_id="operation-1",
            execution_policy=_policy(
                fallback=fallback
            ),
            required_capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        )
    )


def _provider(
    *,
    routing: _Routing,
    operations: _Operations,
    legacy: _LegacyProvider | None = None,
    durations: tuple[
        float,
        ...,
    ] = (
        10.0,
        10.1,
    ),
) -> EnterpriseRoutingAwareRewriteProvider:
    duration_values = iter(
        durations
    )

    return EnterpriseRoutingAwareRewriteProvider(
        legacy_provider=(
            legacy
            or _LegacyProvider()
        ),
        routing=routing,
        catalog=_Catalog(),
        operations=operations,
        evidence_id_factory=(
            lambda: "routing-evidence-1"
        ),
        clock=(
            lambda: NOW
        ),
        duration_clock=(
            lambda: next(
                duration_values
            )
        ),
    )


def test_inactive_context_preserves_legacy_provider() -> None:
    legacy = _LegacyProvider()
    operations = _Operations()

    provider = _provider(
        routing=_Routing(),
        operations=operations,
        legacy=legacy,
    )

    request = rewrite_request()

    result = provider.rewrite(
        request
    )

    assert result.provider_name == "legacy"
    assert legacy.calls == 1
    assert operations.reserved == []
    assert operations.confirmed == []


def test_selected_route_reserves_confirms_and_maps_summary() -> None:
    operations = _Operations()

    routing = _Routing(
        result=ProviderRoutingSelectedResult(
            decision=object(),
            execution=(
                ProviderRoutingExecutionResult(
                    provider_result=_provider_result(
                        provider_name="provider-1",
                        model_name="model-1",
                    ),
                    initial_target_id="target-1",
                    executed_target_id="target-1",
                    execution_fallback_used=False,
                    attempts=(
                        ProviderExecutionAttempt(
                            target_id="target-1",
                            outcome=(
                                ProviderExecutionAttemptOutcome
                                .SUCCEEDED
                            ),
                        ),
                    ),
                )
            ),
        )
    )

    provider = _provider(
        routing=routing,
        operations=operations,
    )

    with provider.use_routing_context(
        _context()
    ):
        result = provider.rewrite(
            rewrite_request()
        )

    assert operations.reserved == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]

    assert operations.confirmed == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]

    assert (
        routing.calls[0][
            "evidence_id"
        ]
        == "routing-evidence-1"
    )

    requirement = routing.calls[0][
        "requirement"
    ]

    assert (
        requirement.required_capabilities
        == frozenset(
            {
                ProviderCapability.REWRITE,
            }
        )
    )

    assert (
        result.primary_provider_name
        == "provider-1"
    )
    assert result.provider_name == "provider-1"
    assert result.fallback_used is False
    assert result.provider_error_category is None
    assert result.latency_ms == 100.0


def test_fallback_route_maps_initial_provider_and_failure_category() -> None:
    operations = _Operations()

    routing = _Routing(
        result=ProviderRoutingSelectedResult(
            decision=object(),
            execution=(
                ProviderRoutingExecutionResult(
                    provider_result=_provider_result(
                        provider_name="provider-2",
                        model_name="model-2",
                    ),
                    initial_target_id="target-1",
                    executed_target_id="target-2",
                    execution_fallback_used=True,
                    attempts=(
                        ProviderExecutionAttempt(
                            target_id="target-1",
                            outcome=(
                                ProviderExecutionAttemptOutcome
                                .PROVIDER_ERROR
                            ),
                            failure_category=(
                                RoutingFailureCategory.TRANSPORT
                            ),
                        ),
                        ProviderExecutionAttempt(
                            target_id="target-2",
                            outcome=(
                                ProviderExecutionAttemptOutcome
                                .SUCCEEDED
                            ),
                        ),
                    ),
                )
            ),
        )
    )

    provider = _provider(
        routing=routing,
        operations=operations,
        durations=(
            20.0,
            20.125,
        ),
    )

    with provider.use_routing_context(
        _context(
            fallback=True
        )
    ):
        result = provider.rewrite(
            rewrite_request()
        )

    assert result.provider_name == "provider-2"
    assert (
        result.primary_provider_name
        == "provider-1"
    )
    assert result.fallback_used is True
    assert (
        result.provider_error_category
        == "transport"
    )
    assert result.latency_ms == 125.0


def test_no_eligible_target_confirms_evidence_then_fails() -> None:
    operations = _Operations()

    routing = _Routing(
        result=ProviderRoutingNotExecutedResult(
            decision=object(),
            evidence=SimpleNamespace(
                evidence_id="routing-evidence-1"
            ),
        )
    )

    provider = _provider(
        routing=routing,
        operations=operations,
    )

    with provider.use_routing_context(
        _context()
    ):
        with pytest.raises(
            EnterpriseProviderRoutingNoEligibleTargetError,
            match="no eligible provider target",
        ):
            provider.rewrite(
                rewrite_request()
            )

    assert operations.reserved == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]
    assert operations.confirmed == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]


def test_provider_failure_confirms_evidence_before_reraise() -> None:
    operations = _Operations()

    routing = _Routing(
        error=RewriteProviderTransportError(
            "provider unavailable"
        )
    )

    provider = _provider(
        routing=routing,
        operations=operations,
    )

    with provider.use_routing_context(
        _context()
    ):
        with pytest.raises(
            RewriteProviderTransportError,
            match="provider unavailable",
        ):
            provider.rewrite(
                rewrite_request()
            )

    assert operations.reserved == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]
    assert operations.confirmed == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]


def test_pre_evidence_runtime_failure_leaves_binding_reserved() -> None:
    operations = _Operations()

    routing = _Routing(
        error=RuntimeError(
            "routing integrity failure"
        )
    )

    provider = _provider(
        routing=routing,
        operations=operations,
    )

    with provider.use_routing_context(
        _context()
    ):
        with pytest.raises(
            RuntimeError,
            match="routing integrity failure",
        ):
            provider.rewrite(
                rewrite_request()
            )

    assert operations.reserved == [
        (
            "operation-1",
            "routing-evidence-1",
        )
    ]
    assert operations.confirmed == []


def test_routing_context_is_reset_after_scope() -> None:
    legacy = _LegacyProvider()
    operations = _Operations()

    routing = _Routing(
        result=ProviderRoutingSelectedResult(
            decision=object(),
            execution=(
                ProviderRoutingExecutionResult(
                    provider_result=_provider_result(
                        provider_name="provider-1",
                        model_name="model-1",
                    ),
                    initial_target_id="target-1",
                    executed_target_id="target-1",
                    execution_fallback_used=False,
                    attempts=(
                        ProviderExecutionAttempt(
                            target_id="target-1",
                            outcome=(
                                ProviderExecutionAttemptOutcome
                                .SUCCEEDED
                            ),
                        ),
                    ),
                )
            ),
        )
    )

    provider = _provider(
        routing=routing,
        operations=operations,
        legacy=legacy,
    )

    with provider.use_routing_context(
        _context()
    ):
        provider.rewrite(
            rewrite_request()
        )

    provider.rewrite(
        rewrite_request()
    )

    assert len(routing.calls) == 1
    assert legacy.calls == 1
