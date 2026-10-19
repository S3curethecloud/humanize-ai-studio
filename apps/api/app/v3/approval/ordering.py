"""Deterministic normalization for Humanize V3.6 approval evidence."""

from __future__ import annotations

from .contracts import ApprovalDecision
from .identity import approval_decision_id


def normalize_decisions(
    decisions: tuple[ApprovalDecision, ...],
) -> tuple[tuple[ApprovalDecision, ...], bool]:
    by_identity: dict[str, ApprovalDecision] = {}
    for decision in decisions:
        decision_id = approval_decision_id(decision)
        by_identity.setdefault(decision_id, decision)

    normalized = tuple(
        sorted(
            by_identity.values(),
            key=lambda decision: (
                decision.approver_id,
                approval_decision_id(decision),
            ),
        )
    )

    by_approver: dict[str, set[str]] = {}
    for decision in normalized:
        by_approver.setdefault(decision.approver_id, set()).add(
            approval_decision_id(decision)
        )

    conflict = any(len(ids) > 1 for ids in by_approver.values())
    return normalized, conflict
