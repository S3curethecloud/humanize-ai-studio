"""Adversarial and environment-independence tests for Humanize V3.6 approval."""

from __future__ import annotations

from dataclasses import replace
import locale
import socket
import time

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


def test_case_10_v35_block_fails_closed() -> None:
    source, request, policy = _source_and_request(
        disposition=AuthorityDisposition.BLOCK
    )
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(_binding(),),
        decisions=(),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.SOURCE_BLOCK,)


def test_case_11_v35_error_fails_closed() -> None:
    source, request, policy = _source_and_request(
        disposition=AuthorityDisposition.ERROR
    )
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(_binding(),),
        decisions=(),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.SOURCE_ERROR,)


def test_case_14_changed_composition_hash_with_old_request_errors() -> None:
    source, request, policy = _source_and_request()
    stale = replace(request, composition_hash=_hex("changed"))
    result = evaluate_approval(
        source=source,
        request=stale,
        policy=policy,
        authority_bindings=(_binding(),),
        decisions=(),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.STALE_COMPOSITION,)


def test_case_15_changed_policy_hash_with_old_request_errors() -> None:
    old_policy = _policy(ids=("alice",), threshold=1)
    source, request, _ = _source_and_request(policy=old_policy)
    new_policy = _policy(ids=("alice", "bob"), threshold=1)
    result = evaluate_approval(
        source=source,
        request=request,
        policy=new_policy,
        authority_bindings=(_binding("alice"), _binding("bob")),
        decisions=(),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (
        ApprovalFailureCode.APPROVAL_POLICY_MISMATCH,
    )


def test_case_19_conflicting_decisions_from_same_approver_error() -> None:
    source, request, policy = _source_and_request()
    binding = _binding()
    approve = _decision(
        request,
        binding,
        kind=ApprovalDecisionKind.APPROVE,
        evidence="approve",
    )
    reject = _decision(
        request,
        binding,
        kind=ApprovalDecisionKind.REJECT,
        evidence="reject",
    )
    result = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(approve, reject),
    )
    assert result.approval_state is ApprovalState.ERROR
    assert result.failure_codes == (ApprovalFailureCode.CONFLICTING_DECISION,)


def _baseline() -> tuple[
    CompositionDecision,
    ApprovalRequest,
    ApprovalPolicy,
    ApproverAuthorityBinding,
    ApprovalDecision,
]:
    source, request, policy = _source_and_request()
    binding = _binding()
    return source, request, policy, binding, _decision(request, binding)


def test_case_33_host_time_change_has_no_semantic_effect(monkeypatch) -> None:
    source, request, policy, binding, decision = _baseline()
    first = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    monkeypatch.setattr(time, "time", lambda: 9_999_999_999.0)
    second = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    assert second == first


def test_case_34_locale_change_has_no_semantic_effect(monkeypatch) -> None:
    source, request, policy, binding, decision = _baseline()
    first = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    monkeypatch.setattr(locale, "getlocale", lambda *args, **kwargs: ("zz_ZZ", "UTF-8"))
    second = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    assert second == first


def test_case_35_filesystem_change_has_no_semantic_effect(tmp_path) -> None:
    source, request, policy, binding, decision = _baseline()
    first = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    (tmp_path / "noise.txt").write_text("changed", encoding="utf-8")
    second = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    assert second == first


def test_case_36_provider_network_availability_has_no_semantic_effect(
    monkeypatch,
) -> None:
    source, request, policy, binding, decision = _baseline()
    first = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )

    def unavailable(*args, **kwargs):
        raise OSError("network unavailable")

    monkeypatch.setattr(socket, "create_connection", unavailable)
    second = evaluate_approval(
        source=source,
        request=request,
        policy=policy,
        authority_bindings=(binding,),
        decisions=(decision,),
    )
    assert second == first
