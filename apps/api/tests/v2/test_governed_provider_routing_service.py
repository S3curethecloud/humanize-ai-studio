from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.domain.models import RewriteRequest
from app.providers.exceptions import (
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    RoutingCandidate,
    RoutingCandidateIneligibilityReason,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceRecord,
)
from app.v2.services.governed_provider_routing_execution_service import (
    GovernedProviderRoutingExecutionService,
)
from app.v2.services.governed_provider_routing_service import (
    GovernedProviderRoutingService,
    ProviderRoutingNotExecutedResult,
    ProviderRoutingSelectedResult,
)
from app.v2.services.provider_routing_decision_service import (
    ProviderRoutingDecisionService,
    ProviderRoutingResolutionError,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderRoutingExecutionResult,
)
from app.v2.services.routing_decision_evidence_service import (
    RoutingDecisionEvidenceService,
)


def _policy() -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=("primary",),
    )


def _selected_decision() -> RoutingDecision:
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


def _no_eligible_decision() -> RoutingDecision:
    return RoutingDecision(
        policy_id="policy",
        status=RoutingDecisionStatus.NO_ELIGIBLE_TARGET,
        reason=RoutingDecisionReason.NO_ELIGIBLE_TARGET,
        candidates=(
            RoutingCandidate(
                target_id="primary",
                eligible=False,
                ineligibility_reasons=(
                    RoutingCandidateIneligibilityReason.TARGET_DISABLED,
                ),
            ),
        ),
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        17,
        0,
        tzinfo=UTC,
    )


def _request() -> RewriteRequest:
    return MagicMock(
        spec=RewriteRequest,
    )


def _services() -> tuple[
    GovernedProviderRoutingService,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    decision = MagicMock(
        spec=ProviderRoutingDecisionService,
    )
    execution = MagicMock(
        spec=GovernedProviderRoutingExecutionService,
    )
    non_execution_evidence = MagicMock(
        spec=RoutingDecisionEvidenceService,
    )

    service = GovernedProviderRoutingService(
        decision=decision,
        execution=execution,
        non_execution_evidence=non_execution_evidence,
    )

    return (
        service,
        decision,
        execution,
        non_execution_evidence,
    )


def test_selected_decision_executes_through_governed_boundary() -> None:
    (
        service,
        decision_service,
        execution_service,
        non_execution_evidence,
    ) = _services()

    policy = _policy()
    requirement = RoutingRequirement()
    request = _request()
    decision = _selected_decision()
    execution = MagicMock(
        spec=ProviderRoutingExecutionResult,
    )

    decision_service.evaluate.return_value = decision
    execution_service.execute.return_value = execution

    result = service.route_and_execute(
        evidence_id="routing-selected",
        policy=policy,
        requirement=requirement,
        request=request,
        observed_at=_observed_at(),
    )

    assert isinstance(
        result,
        ProviderRoutingSelectedResult,
    )
    assert result.decision is decision
    assert result.execution is execution

    decision_service.evaluate.assert_called_once_with(
        policy=policy,
        requirement=requirement,
    )
    execution_service.execute.assert_called_once_with(
        evidence_id="routing-selected",
        policy=policy,
        decision=decision,
        request=request,
        observed_at=_observed_at(),
    )
    non_execution_evidence.record_not_executed.assert_not_called()


def test_no_eligible_target_records_without_execution() -> None:
    (
        service,
        decision_service,
        execution_service,
        non_execution_evidence,
    ) = _services()

    policy = _policy()
    requirement = RoutingRequirement()
    request = _request()
    decision = _no_eligible_decision()
    evidence = MagicMock(
        spec=RoutingEvidenceRecord,
    )

    decision_service.evaluate.return_value = decision
    non_execution_evidence.record_not_executed.return_value = evidence

    result = service.route_and_execute(
        evidence_id="routing-not-executed",
        policy=policy,
        requirement=requirement,
        request=request,
        observed_at=_observed_at(),
    )

    assert isinstance(
        result,
        ProviderRoutingNotExecutedResult,
    )
    assert result.decision is decision
    assert result.evidence is evidence

    decision_service.evaluate.assert_called_once_with(
        policy=policy,
        requirement=requirement,
    )
    non_execution_evidence.record_not_executed.assert_called_once_with(
        evidence_id="routing-not-executed",
        policy=policy,
        decision=decision,
        observed_at=_observed_at(),
    )
    execution_service.execute.assert_not_called()


def test_provider_failure_from_governed_execution_propagates_exactly() -> None:
    (
        service,
        decision_service,
        execution_service,
        non_execution_evidence,
    ) = _services()

    policy = _policy()
    requirement = RoutingRequirement()
    request = _request()
    decision = _selected_decision()
    error = RewriteProviderTransportError(
        "provider unavailable",
    )

    decision_service.evaluate.return_value = decision
    execution_service.execute.side_effect = error

    with pytest.raises(
        RewriteProviderTransportError,
    ) as captured:
        service.route_and_execute(
            evidence_id="routing-provider-failure",
            policy=policy,
            requirement=requirement,
            request=request,
            observed_at=_observed_at(),
        )

    assert captured.value is error

    decision_service.evaluate.assert_called_once_with(
        policy=policy,
        requirement=requirement,
    )
    execution_service.execute.assert_called_once_with(
        evidence_id="routing-provider-failure",
        policy=policy,
        decision=decision,
        request=request,
        observed_at=_observed_at(),
    )
    non_execution_evidence.record_not_executed.assert_not_called()


def test_decision_resolution_failure_propagates_without_evidence() -> None:
    (
        service,
        decision_service,
        execution_service,
        non_execution_evidence,
    ) = _services()

    error = ProviderRoutingResolutionError(
        "provider routing catalog lookup failed",
    )
    decision_service.evaluate.side_effect = error

    with pytest.raises(
        ProviderRoutingResolutionError,
    ) as captured:
        service.route_and_execute(
            evidence_id="routing-resolution-failure",
            policy=_policy(),
            requirement=RoutingRequirement(),
            request=_request(),
            observed_at=_observed_at(),
        )

    assert captured.value is error
    execution_service.execute.assert_not_called()
    non_execution_evidence.record_not_executed.assert_not_called()


def test_non_executed_evidence_failure_is_not_suppressed() -> None:
    (
        service,
        decision_service,
        execution_service,
        non_execution_evidence,
    ) = _services()

    decision_service.evaluate.return_value = (
        _no_eligible_decision()
    )

    error = ValueError(
        "routing evidence already exists",
    )
    non_execution_evidence.record_not_executed.side_effect = error

    with pytest.raises(
        ValueError,
        match="already exists",
    ) as captured:
        service.route_and_execute(
            evidence_id="duplicate-routing-evidence",
            policy=_policy(),
            requirement=RoutingRequirement(),
            request=_request(),
            observed_at=_observed_at(),
        )

    assert captured.value is error
    execution_service.execute.assert_not_called()
