from __future__ import annotations

from collections.abc import (
    Callable,
    Iterator,
)
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import (
    dataclass,
    replace,
)
from datetime import (
    UTC,
    datetime,
)
from time import perf_counter
from uuid import uuid4

from app.domain.models import RewriteRequest
from app.providers.base import (
    RewriteProvider,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderError,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.services.enterprise_provider_routing_operation_service import (
    EnterpriseProviderRoutingOperationService,
)
from app.v2.services.governed_provider_routing_service import (
    GovernedProviderRoutingService,
    ProviderRoutingNotExecutedResult,
    ProviderRoutingSelectedResult,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttemptOutcome,
)


class EnterpriseProviderRoutingProviderIntegrityError(
    RuntimeError,
):
    pass


class EnterpriseProviderRoutingNoEligibleTargetError(
    RuntimeError,
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseProviderRoutingProviderContext:
    operation_id: str
    execution_policy: RoutingPolicy
    required_capabilities: frozenset[
        ProviderCapability
    ]

    def __post_init__(
        self,
    ) -> None:
        if (
            not self.operation_id
            or self.operation_id
            != self.operation_id.strip()
        ):
            raise ValueError(
                "enterprise routing provider context "
                "requires a normalized operation_id"
            )

        if (
            ProviderCapability.REWRITE
            not in self.required_capabilities
        ):
            raise ValueError(
                "enterprise routing provider context "
                "requires rewrite capability"
            )


class EnterpriseRoutingAwareRewriteProvider:
    def __init__(
        self,
        *,
        legacy_provider: RewriteProvider,
        routing: GovernedProviderRoutingService,
        catalog: ProviderCatalogRepository,
        operations: EnterpriseProviderRoutingOperationService,
        evidence_id_factory: Callable[
            [],
            str,
        ]
        | None = None,
        clock: Callable[
            [],
            datetime,
        ]
        | None = None,
        duration_clock: Callable[
            [],
            float,
        ] = perf_counter,
    ) -> None:
        self._legacy_provider = legacy_provider
        self._routing = routing
        self._catalog = catalog
        self._operations = operations
        self._evidence_id_factory = (
            evidence_id_factory
            or _default_evidence_id
        )
        self._clock = (
            clock
            or _utc_now
        )
        self._duration_clock = duration_clock

        self._context: ContextVar[
            EnterpriseProviderRoutingProviderContext | None
        ] = ContextVar(
            "enterprise_provider_routing_provider_context",
            default=None,
        )

    @property
    def provider_name(
        self,
    ) -> str:
        return (
            self._legacy_provider.provider_name
        )

    @contextmanager
    def use_routing_context(
        self,
        context: EnterpriseProviderRoutingProviderContext,
    ) -> Iterator[None]:
        token = self._context.set(
            context
        )

        try:
            yield
        finally:
            self._context.reset(
                token
            )

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        context = self._context.get()

        if context is None:
            return self._legacy_provider.rewrite(
                request
            )

        evidence_id = self._new_evidence_id()

        self._operations.reserve_routing_evidence(
            operation_id=context.operation_id,
            evidence_id=evidence_id,
        )

        requirement = RoutingRequirement(
            required_capabilities=(
                context.required_capabilities
            )
        )

        observed_at = self._clock()
        started_at = self._duration_clock()

        try:
            result = self._routing.route_and_execute(
                evidence_id=evidence_id,
                policy=context.execution_policy,
                requirement=requirement,
                request=request,
                observed_at=observed_at,
            )
        except RewriteProviderError:
            self._operations.confirm_routing_evidence(
                operation_id=context.operation_id,
                evidence_id=evidence_id,
            )
            raise

        duration_ms = max(
            0.0,
            (
                self._duration_clock()
                - started_at
            )
            * 1000.0,
        )

        if isinstance(
            result,
            ProviderRoutingNotExecutedResult,
        ):
            if (
                result.evidence.evidence_id
                != evidence_id
            ):
                raise (
                    EnterpriseProviderRoutingProviderIntegrityError(
                        "routing non-execution evidence identity "
                        "does not match reserved evidence identity"
                    )
                )

            self._operations.confirm_routing_evidence(
                operation_id=context.operation_id,
                evidence_id=evidence_id,
            )

            raise (
                EnterpriseProviderRoutingNoEligibleTargetError(
                    "active enterprise routing policy "
                    "produced no eligible provider target"
                )
            )

        if not isinstance(
            result,
            ProviderRoutingSelectedResult,
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "governed routing returned an unsupported "
                    "runtime result"
                )
            )

        self._operations.confirm_routing_evidence(
            operation_id=context.operation_id,
            evidence_id=evidence_id,
        )

        return self._adapt_selected_result(
            result=result,
            duration_ms=duration_ms,
        )

    def _adapt_selected_result(
        self,
        *,
        result: ProviderRoutingSelectedResult,
        duration_ms: float,
    ) -> RewriteProviderResult:
        execution = result.execution

        attempts = execution.attempts

        if not attempts:
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "selected routing execution requires "
                    "at least one execution attempt"
                )
            )

        if (
            attempts[0].target_id
            != execution.initial_target_id
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing initial target does not match "
                    "first execution attempt"
                )
            )

        if (
            attempts[-1].target_id
            != execution.executed_target_id
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing executed target does not match "
                    "final execution attempt"
                )
            )

        if (
            attempts[-1].outcome
            is not ProviderExecutionAttemptOutcome.SUCCEEDED
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "successful routing result must end "
                    "with a successful execution attempt"
                )
            )

        expected_fallback = (
            len(attempts) > 1
        )

        if (
            execution.execution_fallback_used
            is not expected_fallback
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing fallback summary does not match "
                    "execution attempt cardinality"
                )
            )

        primary_provider_name = (
            self._resolve_provider_name(
                execution.initial_target_id
            )
        )

        first_failure_category = next(
            (
                attempt.failure_category
                for attempt in attempts
                if (
                    attempt.failure_category
                    is not None
                )
            ),
            None,
        )

        if (
            execution.execution_fallback_used
            and first_failure_category is None
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing fallback requires a failed "
                    "attempt category"
                )
            )

        if (
            not execution.execution_fallback_used
            and first_failure_category is not None
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "non-fallback routing execution cannot "
                    "contain a failed attempt category"
                )
            )

        return replace(
            execution.provider_result,
            latency_ms=round(
                duration_ms,
                3,
            ),
            primary_provider_name=(
                primary_provider_name
            ),
            fallback_used=(
                execution.execution_fallback_used
            ),
            provider_error_category=(
                first_failure_category.value
                if first_failure_category
                is not None
                else None
            ),
        )

    def _resolve_provider_name(
        self,
        target_id: str,
    ) -> str:
        try:
            target = self._catalog.get(
                target_id
            )
        except Exception as exc:
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing summary provider catalog "
                    "lookup failed"
                )
            ) from exc

        if target is None:
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing summary initial target is "
                    "absent from provider catalog"
                )
            )

        if target.target_id != target_id:
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing summary provider catalog "
                    "returned mismatched target identity"
                )
            )

        return target.provider.provider_id

    def _new_evidence_id(
        self,
    ) -> str:
        evidence_id = (
            self._evidence_id_factory()
        )

        if (
            not isinstance(
                evidence_id,
                str,
            )
            or not evidence_id.strip()
            or evidence_id
            != evidence_id.strip()
        ):
            raise (
                EnterpriseProviderRoutingProviderIntegrityError(
                    "routing evidence identity factory "
                    "returned an invalid identifier"
                )
            )

        return evidence_id


def _default_evidence_id(
) -> str:
    return (
        "routing_evidence_"
        f"{uuid4().hex}"
    )


def _utc_now(
) -> datetime:
    return datetime.now(
        UTC
    )
