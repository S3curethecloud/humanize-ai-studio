"""Authority validation for Humanize V3.6 approval."""

from __future__ import annotations

from app.v3.composition.contracts import GovernedComposition

from .contracts import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalFailureCode,
    ApprovalPolicy,
    ApprovalRequest,
    ApproverAuthorityBinding,
)
from .identity import (
    approval_decision_id,
    approver_authority_hash,
    is_sha256_hex,
)


def scope_failure(
    request: ApprovalRequest,
    composition: GovernedComposition,
    bindings: tuple[ApproverAuthorityBinding, ...],
) -> ApprovalFailureCode | None:
    if request.tenant_id != composition.tenant_id:
        return ApprovalFailureCode.TENANT_MISMATCH
    if request.engagement_id != composition.engagement_id:
        return ApprovalFailureCode.ENGAGEMENT_MISMATCH

    ordered = sorted(
        bindings,
        key=lambda binding: (
            str(binding.approver_id),
            approver_authority_hash(binding),
        ),
    )
    for binding in ordered:
        if binding.tenant_id != request.tenant_id:
            return ApprovalFailureCode.TENANT_MISMATCH
        if binding.engagement_id != request.engagement_id:
            return ApprovalFailureCode.ENGAGEMENT_MISMATCH
    return None


def validate_authority_bindings(
    policy: ApprovalPolicy,
    bindings: tuple[ApproverAuthorityBinding, ...],
) -> tuple[dict[str, ApproverAuthorityBinding] | None, ApprovalFailureCode | None]:
    normalized: dict[str, ApproverAuthorityBinding] = {}

    for binding in sorted(
        bindings,
        key=lambda item: (str(item.approver_id), approver_authority_hash(item)),
    ):
        if (
            not isinstance(binding.tenant_id, str)
            or not binding.tenant_id.strip()
            or not isinstance(binding.engagement_id, str)
            or not binding.engagement_id.strip()
            or not isinstance(binding.approver_id, str)
            or not binding.approver_id.strip()
            or not isinstance(binding.authority_policy_id, str)
            or not binding.authority_policy_id.strip()
            or not is_sha256_hex(binding.authority_policy_hash)
            or not isinstance(binding.allowed_decisions, tuple)
            or not binding.allowed_decisions
            or not all(
                isinstance(decision, ApprovalDecisionKind)
                for decision in binding.allowed_decisions
            )
            or len(set(binding.allowed_decisions)) != len(binding.allowed_decisions)
            or not isinstance(binding.allowed_requested_scopes, tuple)
            or not binding.allowed_requested_scopes
            or not all(
                isinstance(scope, str) and scope.strip()
                for scope in binding.allowed_requested_scopes
            )
            or len(set(binding.allowed_requested_scopes))
            != len(binding.allowed_requested_scopes)
        ):
            return None, ApprovalFailureCode.AUTHORITY_BINDING_INVALID

        existing = normalized.get(binding.approver_id)
        if existing is not None and existing != binding:
            return None, ApprovalFailureCode.AUTHORITY_BINDING_INVALID
        normalized[binding.approver_id] = binding

    if any(
        approver_id not in normalized
        for approver_id in policy.required_approver_ids
    ):
        return None, ApprovalFailureCode.AUTHORITY_BINDING_INVALID

    return normalized, None


def validate_decisions(
    *,
    request_id: str,
    request: ApprovalRequest,
    policy: ApprovalPolicy,
    bindings: dict[str, ApproverAuthorityBinding],
    decisions: tuple[ApprovalDecision, ...],
) -> ApprovalFailureCode | None:
    ordered = sorted(
        decisions,
        key=lambda decision: (
            str(decision.approver_id),
            approval_decision_id(decision),
        ),
    )

    for decision in ordered:
        if (
            not isinstance(decision.approval_request_id, str)
            or not is_sha256_hex(decision.approval_request_id)
            or not isinstance(decision.approver_id, str)
            or not decision.approver_id.strip()
            or not is_sha256_hex(decision.approver_authority_hash)
            or not isinstance(decision.decision, ApprovalDecisionKind)
            or not isinstance(decision.reason_code, str)
            or not decision.reason_code.strip()
            or not is_sha256_hex(decision.evidence_hash)
        ):
            return ApprovalFailureCode.DECISION_INVALID

        if decision.approval_request_id != request_id:
            return ApprovalFailureCode.DECISION_REQUEST_MISMATCH

        binding = bindings.get(decision.approver_id)
        if (
            binding is None
            or decision.approver_id not in policy.required_approver_ids
        ):
            return ApprovalFailureCode.UNKNOWN_APPROVER

        if request.requested_scope not in binding.allowed_requested_scopes:
            return ApprovalFailureCode.UNAUTHORIZED_SCOPE

        if decision.decision not in binding.allowed_decisions:
            return ApprovalFailureCode.UNAUTHORIZED_DECISION

        if decision.approver_authority_hash != approver_authority_hash(binding):
            return ApprovalFailureCode.APPROVER_AUTHORITY_HASH_MISMATCH

    return None
