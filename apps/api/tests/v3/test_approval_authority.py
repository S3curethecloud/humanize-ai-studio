"""Approver-authority tests for Humanize V3.6 approval."""

from __future__ import annotations

import hashlib

from app.v3.authority.contracts import AuthorityDisposition
from app.v3.approval import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalFailureCode,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalState,
    ApproverAuthorityBinding,
    approval_policy_hash,
    approval_request_id,
    approver_authority_hash,
    evaluate_approval,
)
from app.v3.composition.contracts import (
    CompositionDecision,
    CompositionEvidence,
    CompositionKind,
    GovernedComposition,
)

def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _policy(
    *,
    ids: tuple[str, ...] = ("alice",),
    threshold: int = 1,
    policy_id: str = "policy-1",
) -> ApprovalPolicy:
    return ApprovalPolicy(
        approval_policy_id=policy_id,
        approval_policy_hash=approval_policy_hash(policy_id, ids, threshold),
        required_approver_ids=ids,
        approval_threshold=threshold,
    )


def _source_and_request(
    *,
    disposition: AuthorityDisposition = AuthorityDisposition.ELIGIBLE,
    tenant_id: str = "tenant-a",
    engagement_id: str = "eng-a",
    seed: str = "base",
    policy: ApprovalPolicy | None = None,
    requested_scope: str = "release",
) -> tuple[CompositionDecision, ApprovalRequest, ApprovalPolicy]:
    selected_policy = policy or _policy()
    digest = _hex(seed)
    composition_id = f"composition:sha256:{digest}"
    composition = None
    if disposition in (
        AuthorityDisposition.ELIGIBLE,
        AuthorityDisposition.PRESENTATION_ONLY,
    ):
        composition = GovernedComposition(
            composition_id=composition_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            entries=(),
            aggregate_classification=None,
            provenance_ledger=(),
            source_authority_ledger=(),
            protected_fact_refs=(),
            presentation_derivation_refs=(),
            kind=(
                CompositionKind.PRESENTATION
                if disposition is AuthorityDisposition.PRESENTATION_ONLY
                else CompositionKind.AUTHORITATIVE
            ),
            disposition=disposition,
            evidence=CompositionEvidence(
                ordered_input_ids=(),
                input_evidence=(),
                issues=(),
            ),
        )
    source = CompositionDecision(
        disposition=disposition,
        composition=composition,
        issues=(),
        evidence=CompositionEvidence(
            ordered_input_ids=(),
            input_evidence=(),
            issues=(),
        ),
    )
    request = ApprovalRequest(
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        composition_id=composition_id,
        composition_hash=digest,
        composition_disposition=disposition,
        approval_policy_id=selected_policy.approval_policy_id,
        approval_policy_hash=selected_policy.approval_policy_hash,
        requested_scope=requested_scope,
    )
    return source, request, selected_policy


def _binding(
    approver_id: str = "alice",
    *,
    tenant_id: str = "tenant-a",
    engagement_id: str = "eng-a",
    scopes: tuple[str, ...] = ("release",),
    decisions: tuple[ApprovalDecisionKind, ...] = (
        ApprovalDecisionKind.APPROVE,
        ApprovalDecisionKind.REJECT,
        ApprovalDecisionKind.REQUIRE_REVISION,
    ),
) -> ApproverAuthorityBinding:
    return ApproverAuthorityBinding(
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        approver_id=approver_id,
        authority_policy_id="authority-policy-1",
        authority_policy_hash=_hex("authority-policy-1"),
        allowed_decisions=decisions,
        allowed_requested_scopes=scopes,
    )


def _decision(
    request: ApprovalRequest,
    binding: ApproverAuthorityBinding,
    *,
    kind: ApprovalDecisionKind = ApprovalDecisionKind.APPROVE,
    reason: str = "reviewed",
    evidence: str = "evidence-1",
    approver_id: str | None = None,
    authority_hash: str | None = None,
) -> ApprovalDecision:
    return ApprovalDecision(
        approval_request_id=approval_request_id(request),
        approver_id=approver_id or binding.approver_id,
        approver_authority_hash=(
            authority_hash
            if authority_hash is not None
            else approver_authority_hash(binding)
        ),
        decision=kind,
        reason_code=reason,
        evidence_hash=_hex(evidence),
    )


def test_case_16_unknown_approver_errors() -> None:
    source, request, policy = _source_and_request()
    alice = _binding("alice")
    unknown = _binding("bob")
    decision = _decision(request, unknown)
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(alice,),
        decisions=(decision,),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.UNKNOWN_APPROVER,)


def test_case_17_unauthorized_requested_scope_errors() -> None:
    source, request, policy = _source_and_request(requested_scope="publish")
    binding = _binding(scopes=("release",))
    decision = _decision(request, binding)
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.UNAUTHORIZED_SCOPE,)


def test_case_18_unauthorized_decision_type_errors() -> None:
    source, request, policy = _source_and_request()
    binding = _binding(decisions=(ApprovalDecisionKind.APPROVE,))
    decision = _decision(
        request,
        binding,
        kind=ApprovalDecisionKind.REJECT,
    )
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.UNAUTHORIZED_DECISION,)
