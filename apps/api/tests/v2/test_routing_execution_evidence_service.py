from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceAttemptOutcome,
    RoutingEvidenceExecutionOutcome,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttempt,
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionFailureResult,
    ProviderRoutingExecutionResult,
)
from app.v2.services.routing_execution_evidence_service import (
    RoutingExecutionEvidenceIntegrityError,
    RoutingExecutionEvidenceService,
)


def _policy(
    *target_ids: str,
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
            failure_categories=(
                RoutingFailureCategory.TRANSPORT,
            ),
        ),
    )


def _decision(
    *target_ids: str,
    selected_target_id: str = "primary",
) -> RoutingDecision:
    selected_index = target_ids.index(
        selected_target_id
    )

    return RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=(
            RoutingDecisionReason.PRIMARY_SELECTED
            if selected_index == 0
            else RoutingDecisionReason.FALLBACK_SELECTED
        ),
        selected_target_id=selected_target_id,
        candidates=tuple(
            RoutingCandidate(
                target_id=target_id,
                eligible=True,
            )
            for target_id in target_ids
        ),
    )


def _provider_result(
    target_id: str,
) -> RewriteProviderResult:
    return RewriteProviderResult(
        text=f"result from {target_id}",
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


def _success_attempt(
    target_id: str,
) -> ProviderExecutionAttempt:
    return ProviderExecutionAttempt(
        target_id=target_id,
        outcome=(
            ProviderExecutionAttemptOutcome.SUCCEEDED
        ),
    )


def _failure_attempt(
    target_id: str,
    *,
    category: RoutingFailureCategory = (
        RoutingFailureCategory.TRANSPORT
    ),
) -> ProviderExecutionAttempt:
    return ProviderExecutionAttempt(
        target_id=target_id,
        outcome=(
            ProviderExecutionAttemptOutcome.PROVIDER_ERROR
        ),
        failure_category=category,
    )


def _service(
) -> tuple[
    RoutingExecutionEvidenceService,
    InMemoryRoutingEvidenceRepository,
]:
    repository = InMemoryRoutingEvidenceRepository()

    return (
        RoutingExecutionEvidenceService(
            repository=repository,
        ),
        repository,
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )


def test_records_successful_primary_execution() -> None:
    service, repository = _service()

    outcome = ProviderRoutingExecutionResult(
        provider_result=_provider_result("primary"),
        initial_target_id="primary",
        executed_target_id="primary",
        execution_fallback_used=False,
        attempts=(
            _success_attempt("primary"),
        ),
    )

    record = service.record(
        evidence_id="evidence-1",
        policy=_policy("primary"),
        decision=_decision("primary"),
        outcome=outcome,
        observed_at=_observed_at(),
    )

    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )
    assert record.executed_target_id == "primary"
    assert record.execution_fallback_used is False
    assert len(record.attempts) == 1
    assert (
        repository.get("evidence-1")
        == record
    )


def test_records_successful_execution_fallback() -> None:
    service, _ = _service()

    outcome = ProviderRoutingExecutionResult(
        provider_result=_provider_result("fallback"),
        initial_target_id="primary",
        executed_target_id="fallback",
        execution_fallback_used=True,
        attempts=(
            _failure_attempt("primary"),
            _success_attempt("fallback"),
        ),
    )

    record = service.record(
        evidence_id="evidence-fallback",
        policy=_policy(
            "primary",
            "fallback",
        ),
        decision=_decision(
            "primary",
            "fallback",
        ),
        outcome=outcome,
        observed_at=_observed_at(),
    )

    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.SUCCEEDED
    )
    assert record.executed_target_id == "fallback"
    assert record.execution_fallback_used is True

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
        record.attempts[1].outcome
        is RoutingEvidenceAttemptOutcome.SUCCEEDED
    )


def test_records_terminal_provider_failure() -> None:
    service, repository = _service()

    error = RewriteProviderTransportError(
        "terminal"
    )

    outcome = ProviderRoutingExecutionFailureResult(
        error=error,
        initial_target_id="primary",
        attempts=(
            _failure_attempt("primary"),
        ),
    )

    record = service.record(
        evidence_id="evidence-failed",
        policy=_policy("primary"),
        decision=_decision("primary"),
        outcome=outcome,
        observed_at=_observed_at(),
    )

    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.FAILED
    )
    assert record.executed_target_id is None
    assert record.execution_fallback_used is False
    assert (
        record.attempts[0].failure_category
        is RoutingFailureCategory.TRANSPORT
    )
    assert (
        repository.get("evidence-failed")
        == record
    )


def test_records_multiple_failed_attempts() -> None:
    service, _ = _service()

    outcome = ProviderRoutingExecutionFailureResult(
        error=RewriteProviderTransportError(
            "final"
        ),
        initial_target_id="primary",
        attempts=(
            _failure_attempt("primary"),
            _failure_attempt("fallback"),
        ),
    )

    record = service.record(
        evidence_id="evidence-all-failed",
        policy=_policy(
            "primary",
            "fallback",
        ),
        decision=_decision(
            "primary",
            "fallback",
        ),
        outcome=outcome,
        observed_at=_observed_at(),
    )

    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.FAILED
    )
    assert record.execution_fallback_used is True

    assert tuple(
        attempt.target_id
        for attempt in record.attempts
    ) == (
        "primary",
        "fallback",
    )


@pytest.mark.parametrize(
    "category",
    [
        RoutingFailureCategory.CONFIGURATION,
        RoutingFailureCategory.TRANSPORT,
        RoutingFailureCategory.RESPONSE,
        RoutingFailureCategory.PROVIDER,
    ],
)
def test_preserves_provider_failure_category(
    category: RoutingFailureCategory,
) -> None:
    service, _ = _service()

    outcome = ProviderRoutingExecutionFailureResult(
        error=RewriteProviderTransportError(
            "provider failure"
        ),
        initial_target_id="primary",
        attempts=(
            _failure_attempt(
                "primary",
                category=category,
            ),
        ),
    )

    record = service.record(
        evidence_id=f"evidence-{category.value}",
        policy=_policy("primary"),
        decision=_decision("primary"),
        outcome=outcome,
        observed_at=_observed_at(),
    )

    assert (
        record.attempts[0].failure_category
        is category
    )


def test_observed_timestamp_is_caller_supplied() -> None:
    service, _ = _service()

    observed_at = datetime(
        2026,
        8,
        17,
        8,
        30,
        tzinfo=UTC,
    )

    record = service.record(
        evidence_id="evidence-time",
        policy=_policy("primary"),
        decision=_decision("primary"),
        outcome=ProviderRoutingExecutionResult(
            provider_result=_provider_result("primary"),
            initial_target_id="primary",
            executed_target_id="primary",
            execution_fallback_used=False,
            attempts=(
                _success_attempt("primary"),
            ),
        ),
        observed_at=observed_at,
    )

    assert record.observed_at == observed_at


def test_duplicate_evidence_id_is_not_suppressed() -> None:
    service, repository = _service()

    outcome = ProviderRoutingExecutionResult(
        provider_result=_provider_result("primary"),
        initial_target_id="primary",
        executed_target_id="primary",
        execution_fallback_used=False,
        attempts=(
            _success_attempt("primary"),
        ),
    )

    first = service.record(
        evidence_id="duplicate",
        policy=_policy("primary"),
        decision=_decision("primary"),
        outcome=outcome,
        observed_at=_observed_at(),
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        service.record(
            evidence_id="duplicate",
            policy=_policy("primary"),
            decision=_decision("primary"),
            outcome=outcome,
            observed_at=_observed_at(),
        )

    assert repository.get("duplicate") == first


def test_initial_target_mismatch_fails_before_persistence() -> None:
    service, repository = _service()

    outcome = ProviderRoutingExecutionResult(
        provider_result=_provider_result("other"),
        initial_target_id="other",
        executed_target_id="other",
        execution_fallback_used=False,
        attempts=(
            _success_attempt("other"),
        ),
    )

    with pytest.raises(
        RoutingExecutionEvidenceIntegrityError,
        match="initial target",
    ):
        service.record(
            evidence_id="bad-identity",
            policy=_policy("primary"),
            decision=_decision("primary"),
            outcome=outcome,
            observed_at=_observed_at(),
        )

    assert repository.get("bad-identity") is None


def test_domain_integrity_rejects_invalid_attempt_order() -> None:
    service, repository = _service()

    outcome = ProviderRoutingExecutionResult(
        provider_result=_provider_result("fallback"),
        initial_target_id="primary",
        executed_target_id="fallback",
        execution_fallback_used=True,
        attempts=(
            _failure_attempt("fallback"),
            _success_attempt("primary"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="execution attempts",
    ):
        service.record(
            evidence_id="bad-order",
            policy=_policy(
                "primary",
                "fallback",
            ),
            decision=_decision(
                "primary",
                "fallback",
            ),
            outcome=outcome,
            observed_at=_observed_at(),
        )

    assert repository.get("bad-order") is None


def test_domain_integrity_rejects_false_fallback_flag() -> None:
    service, repository = _service()

    outcome = ProviderRoutingExecutionResult(
        provider_result=_provider_result("fallback"),
        initial_target_id="primary",
        executed_target_id="fallback",
        execution_fallback_used=False,
        attempts=(
            _failure_attempt("primary"),
            _success_attempt("fallback"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="execution_fallback_used",
    ):
        service.record(
            evidence_id="bad-fallback",
            policy=_policy(
                "primary",
                "fallback",
            ),
            decision=_decision(
                "primary",
                "fallback",
            ),
            outcome=outcome,
            observed_at=_observed_at(),
        )

    assert repository.get("bad-fallback") is None
