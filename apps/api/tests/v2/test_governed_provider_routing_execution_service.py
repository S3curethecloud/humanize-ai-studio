from __future__ import annotations

from datetime import UTC, datetime
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
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.governed_provider_routing_execution_service import (
    GovernedProviderRoutingExecutionService,
)
from app.v2.services.provider_execution_adapter import (
    ProviderExecutionIntegrityError,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttempt,
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionFailureResult,
    ProviderRoutingExecutionResult,
    ProviderRoutingExecutionService,
)
from app.v2.services.routing_execution_evidence_service import (
    RoutingExecutionEvidenceService,
)


def _policy() -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=("primary",),
    )


def _decision() -> RoutingDecision:
    return RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="primary",
        candidates=(
            RoutingCandidate(
                target_id="primary",
                eligible=True,
            ),
        ),
    )


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="Original text.",
        audience="general",
        tone="professional",
        intensity=RewriteIntensity.NATURAL_REWRITE,
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        15,
        0,
        tzinfo=UTC,
    )


def _provider_result() -> RewriteProviderResult:
    return RewriteProviderResult(
        text="Rewritten text.",
        changes=[],
        provider_name="provider-primary",
        model_name="model-primary",
        prompt_version="prompt-v1",
        latency_ms=1.0,
        primary_provider_name="provider-primary",
        fallback_used=False,
        provider_error_category=None,
        usage=ProviderUsage(),
    )


def _success_outcome() -> ProviderRoutingExecutionResult:
    return ProviderRoutingExecutionResult(
        provider_result=_provider_result(),
        initial_target_id="primary",
        executed_target_id="primary",
        execution_fallback_used=False,
        attempts=(
            ProviderExecutionAttempt(
                target_id="primary",
                outcome=(
                    ProviderExecutionAttemptOutcome.SUCCEEDED
                ),
            ),
        ),
    )


def _failure_outcome(
    error: RewriteProviderTransportError,
) -> ProviderRoutingExecutionFailureResult:
    return ProviderRoutingExecutionFailureResult(
        error=error,
        initial_target_id="primary",
        attempts=(
            ProviderExecutionAttempt(
                target_id="primary",
                outcome=(
                    ProviderExecutionAttemptOutcome.PROVIDER_ERROR
                ),
                failure_category=(
                    RoutingFailureCategory.TRANSPORT
                ),
            ),
        ),
    )


def _service(
    *,
    execution: ProviderRoutingExecutionService,
) -> tuple[
    GovernedProviderRoutingExecutionService,
    InMemoryRoutingEvidenceRepository,
]:
    repository = InMemoryRoutingEvidenceRepository()

    evidence = RoutingExecutionEvidenceService(
        repository=repository,
    )

    return (
        GovernedProviderRoutingExecutionService(
            execution=execution,
            evidence=evidence,
        ),
        repository,
    )


def test_success_is_persisted_before_return() -> None:
    execution = MagicMock(
        spec=ProviderRoutingExecutionService,
    )
    outcome = _success_outcome()
    execution.execute_outcome.return_value = outcome

    service, repository = _service(
        execution=execution,
    )

    result = service.execute(
        evidence_id="evidence-success",
        policy=_policy(),
        decision=_decision(),
        request=_request(),
        observed_at=_observed_at(),
    )

    assert result is outcome

    record = repository.get("evidence-success")

    assert record is not None
    assert record.executed_target_id == "primary"
    assert record.observed_at == _observed_at()

    execution.execute_outcome.assert_called_once()


def test_terminal_provider_failure_is_persisted_then_reraised_exactly() -> None:
    execution = MagicMock(
        spec=ProviderRoutingExecutionService,
    )

    error = RewriteProviderTransportError(
        "terminal"
    )
    outcome = _failure_outcome(error)

    execution.execute_outcome.return_value = outcome

    service, repository = _service(
        execution=execution,
    )

    with pytest.raises(
        RewriteProviderTransportError,
    ) as exc_info:
        service.execute(
            evidence_id="evidence-failed",
            policy=_policy(),
            decision=_decision(),
            request=_request(),
            observed_at=_observed_at(),
        )

    assert exc_info.value is error

    record = repository.get("evidence-failed")

    assert record is not None
    assert record.executed_target_id is None
    assert len(record.attempts) == 1

    execution.execute_outcome.assert_called_once()


def test_non_provider_execution_failure_is_not_converted_to_evidence() -> None:
    execution = MagicMock(
        spec=ProviderRoutingExecutionService,
    )

    error = ProviderExecutionIntegrityError(
        "integrity"
    )
    execution.execute_outcome.side_effect = error

    service, repository = _service(
        execution=execution,
    )

    with pytest.raises(
        ProviderExecutionIntegrityError,
    ) as exc_info:
        service.execute(
            evidence_id="evidence-integrity",
            policy=_policy(),
            decision=_decision(),
            request=_request(),
            observed_at=_observed_at(),
        )

    assert exc_info.value is error
    assert repository.get("evidence-integrity") is None


def test_evidence_persistence_failure_is_not_suppressed() -> None:
    execution = MagicMock(
        spec=ProviderRoutingExecutionService,
    )
    outcome = _success_outcome()

    execution.execute_outcome.return_value = outcome

    service, repository = _service(
        execution=execution,
    )

    service.execute(
        evidence_id="duplicate",
        policy=_policy(),
        decision=_decision(),
        request=_request(),
        observed_at=_observed_at(),
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        service.execute(
            evidence_id="duplicate",
            policy=_policy(),
            decision=_decision(),
            request=_request(),
            observed_at=_observed_at(),
        )

    assert repository.get("duplicate") is not None
    assert execution.execute_outcome.call_count == 2
