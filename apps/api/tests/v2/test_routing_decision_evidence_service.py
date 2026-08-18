from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.v2.domain.provider_routing import (
    RoutingCandidate,
    RoutingCandidateIneligibilityReason,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.routing_decision_evidence_service import (
    RoutingDecisionEvidenceIntegrityError,
    RoutingDecisionEvidenceService,
)


def _policy() -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="policy",
        ordered_target_ids=("primary",),
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


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        16,
        0,
        tzinfo=UTC,
    )


def _service() -> tuple[
    RoutingDecisionEvidenceService,
    InMemoryRoutingEvidenceRepository,
]:
    repository = InMemoryRoutingEvidenceRepository()

    return (
        RoutingDecisionEvidenceService(
            repository=repository,
        ),
        repository,
    )


def test_records_no_eligible_target_as_not_executed() -> None:
    service, repository = _service()

    record = service.record_not_executed(
        evidence_id="not-executed-1",
        policy=_policy(),
        decision=_no_eligible_decision(),
        observed_at=_observed_at(),
    )

    assert (
        record.execution_outcome
        is RoutingEvidenceExecutionOutcome.NOT_EXECUTED
    )
    assert record.executed_target_id is None
    assert record.execution_fallback_used is False
    assert record.attempts == ()
    assert record.observed_at == _observed_at()

    assert (
        repository.get("not-executed-1")
        == record
    )


def test_selected_decision_is_rejected_before_persistence() -> None:
    service, repository = _service()

    with pytest.raises(
        RoutingDecisionEvidenceIntegrityError,
        match="no-eligible-target",
    ):
        service.record_not_executed(
            evidence_id="selected",
            policy=_policy(),
            decision=_selected_decision(),
            observed_at=_observed_at(),
        )

    assert repository.get("selected") is None


def test_policy_identity_mismatch_is_rejected_by_domain() -> None:
    service, repository = _service()

    mismatched = RoutingPolicy(
        policy_id="other-policy",
        ordered_target_ids=("primary",),
    )

    with pytest.raises(
        ValueError,
        match="policy identity",
    ):
        service.record_not_executed(
            evidence_id="bad-policy",
            policy=mismatched,
            decision=_no_eligible_decision(),
            observed_at=_observed_at(),
        )

    assert repository.get("bad-policy") is None


def test_duplicate_evidence_id_is_not_suppressed() -> None:
    service, repository = _service()

    first = service.record_not_executed(
        evidence_id="duplicate",
        policy=_policy(),
        decision=_no_eligible_decision(),
        observed_at=_observed_at(),
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        service.record_not_executed(
            evidence_id="duplicate",
            policy=_policy(),
            decision=_no_eligible_decision(),
            observed_at=_observed_at(),
        )

    assert repository.get("duplicate") == first
