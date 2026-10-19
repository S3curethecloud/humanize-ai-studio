"""Service acceptance tests for Humanize V3.6 approval."""

from __future__ import annotations

from dataclasses import replace

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


def test_case_01_valid_single_required_approval_is_approved() -> None:
    source, request, policy = _source_and_request()
    binding = _binding()
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(_decision(request, binding),),
    )
    assert result.approval_state is ApprovalState.APPROVED


def test_case_02_threshold_two_with_one_approval_is_pending() -> None:
    policy = _policy(ids=("alice", "bob"), threshold=2)
    source, request, _ = _source_and_request(policy=policy)
    alice, bob = _binding("alice"), _binding("bob")
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(alice, bob),
        decisions=(_decision(request, alice),),
    )
    assert result.approval_state is ApprovalState.PENDING


def test_case_03_threshold_two_with_two_approvals_is_approved() -> None:
    policy = _policy(ids=("alice", "bob"), threshold=2)
    source, request, _ = _source_and_request(policy=policy)
    alice, bob = _binding("alice"), _binding("bob")
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(alice, bob),
        decisions=(
            _decision(request, alice, evidence="a"),
            _decision(request, bob, evidence="b"),
        ),
    )
    assert result.approval_state is ApprovalState.APPROVED


def test_case_04_presentation_only_can_be_approved_without_promotion() -> None:
    source, request, policy = _source_and_request(
        disposition=AuthorityDisposition.PRESENTATION_ONLY
    )
    binding = _binding()
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(_decision(request, binding),),
    )
    assert result.approval_state is ApprovalState.APPROVED
    assert result.source_disposition is AuthorityDisposition.PRESENTATION_ONLY


def test_case_09_revised_composition_does_not_inherit_old_request() -> None:
    source, request, policy = _source_and_request(seed="old")
    binding = _binding()
    revised_source, _, _ = _source_and_request(seed="new", policy=policy)
    result = evaluate_approval(
        source=revised_source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(_decision(request, binding),),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.STALE_COMPOSITION,)


def test_case_26_presentation_approval_never_becomes_protected_fact() -> None:
    source, request, policy = _source_and_request(
        disposition=AuthorityDisposition.PRESENTATION_ONLY
    )
    binding = _binding()
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(_decision(request, binding),),
    )
    assert result.approval_state is ApprovalState.APPROVED
    assert result.source_disposition is AuthorityDisposition.PRESENTATION_ONLY
    assert result.composition_id == request.composition_id


def test_case_28_evaluation_does_not_mutate_v35_source() -> None:
    source, request, policy = _source_and_request()
    original = source
    binding = _binding()
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(_decision(request, binding),),
    )
    assert source == original
    assert source.composition is original.composition
    assert result.composition_id == source.composition.composition_id
