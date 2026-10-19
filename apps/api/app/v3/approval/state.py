"""Pure aggregate state derivation for Humanize V3.6 approval."""

from __future__ import annotations

from .contracts import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalPolicy,
    ApprovalState,
)


def derive_state(
    policy: ApprovalPolicy,
    decisions: tuple[ApprovalDecision, ...],
) -> ApprovalState:
    if any(
        decision.decision is ApprovalDecisionKind.REJECT
        for decision in decisions
    ):
        return ApprovalState.REJECTED

    if any(
        decision.decision is ApprovalDecisionKind.REQUIRE_REVISION
        for decision in decisions
    ):
        return ApprovalState.REVISION_REQUIRED

    approved = {
        decision.approver_id
        for decision in decisions
        if decision.decision is ApprovalDecisionKind.APPROVE
        and decision.approver_id in policy.required_approver_ids
    }
    if len(approved) >= policy.approval_threshold:
        return ApprovalState.APPROVED
    return ApprovalState.PENDING
