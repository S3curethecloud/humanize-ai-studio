"""Deterministic provider-free Humanize V3.6 approval evaluator."""

from __future__ import annotations

from app.v3.authority.contracts import AuthorityDisposition
from app.v3.composition.contracts import CompositionDecision

from .authority import (
    scope_failure,
    validate_authority_bindings,
    validate_decisions,
)
from .contracts import (
    ApprovalDecision,
    ApprovalFailureCode,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResult,
    ApprovalState,
    ApproverAuthorityBinding,
)
from .identity import (
    approval_decision_id,
    approval_policy_hash,
    approval_request_id,
    approval_trace_hash,
    composition_hash_from_id,
    is_sha256_hex,
)
from .ordering import normalize_decisions
from .state import derive_state


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _request_valid(request: ApprovalRequest) -> bool:
    return (
        _nonempty(request.tenant_id)
        and _nonempty(request.engagement_id)
        and _nonempty(request.composition_id)
        and composition_hash_from_id(request.composition_id) is not None
        and is_sha256_hex(request.composition_hash)
        and isinstance(request.composition_disposition, AuthorityDisposition)
        and _nonempty(request.approval_policy_id)
        and is_sha256_hex(request.approval_policy_hash)
        and _nonempty(request.requested_scope)
    )


def _policy_valid(policy: ApprovalPolicy) -> bool:
    ids = policy.required_approver_ids
    if (
        not _nonempty(policy.approval_policy_id)
        or not is_sha256_hex(policy.approval_policy_hash)
        or not isinstance(ids, tuple)
        or not ids
        or not all(_nonempty(approver_id) for approver_id in ids)
        or len(set(ids)) != len(ids)
        or tuple(sorted(ids)) != ids
        or not isinstance(policy.approval_threshold, int)
        or isinstance(policy.approval_threshold, bool)
        or policy.approval_threshold < 1
        or policy.approval_threshold > len(ids)
    ):
        return False

    return policy.approval_policy_hash == approval_policy_hash(
        policy.approval_policy_id,
        policy.required_approver_ids,
        policy.approval_threshold,
    )


def _result(
    *,
    request: ApprovalRequest,
    policy: ApprovalPolicy,
    source_disposition: AuthorityDisposition,
    state: ApprovalState,
    failures: tuple[ApprovalFailureCode, ...] = (),
    normalized_decisions: tuple[ApprovalDecision, ...] = (),
) -> ApprovalResult:
    request_id = approval_request_id(request)
    normalized_ids = tuple(
        approval_decision_id(decision) for decision in normalized_decisions
    )
    ordered_failures = tuple(sorted(set(failures), key=lambda code: code.value))
    return ApprovalResult(
        approval_request_id=request_id,
        composition_id=request.composition_id,
        composition_hash=request.composition_hash,
        source_disposition=source_disposition,
        approval_state=state,
        normalized_decision_ids=normalized_ids,
        approval_trace_hash=approval_trace_hash(
            approval_request_id_value=request_id,
            policy=policy,
            normalized_decisions=normalized_decisions,
            final_state=state,
            failure_codes=ordered_failures,
        ),
        failure_codes=ordered_failures,
    )


def evaluate_approval(
    *,
    source: CompositionDecision,
    request: ApprovalRequest,
    policy: ApprovalPolicy,
    authority_bindings: tuple[ApproverAuthorityBinding, ...],
    decisions: tuple[ApprovalDecision, ...],
) -> ApprovalResult:
    if not _request_valid(request):
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.INVALID_REQUEST,),
        )

    if not _policy_valid(policy):
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.INVALID_POLICY,),
        )

    if source.disposition is AuthorityDisposition.ERROR:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.SOURCE_ERROR,),
        )

    if source.disposition is AuthorityDisposition.BLOCK:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.SOURCE_BLOCK,),
        )

    composition = source.composition
    if composition is None:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.SOURCE_COMPOSITION_MISSING,),
        )

    scope_issue = scope_failure(request, composition, authority_bindings)
    if scope_issue is not None:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(scope_issue,),
        )

    actual_composition_hash = composition_hash_from_id(composition.composition_id)
    if (
        request.composition_id != composition.composition_id
        or request.composition_hash != actual_composition_hash
        or request.composition_disposition is not source.disposition
        or composition.disposition is not source.disposition
    ):
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.STALE_COMPOSITION,),
        )

    if (
        request.approval_policy_id != policy.approval_policy_id
        or request.approval_policy_hash != policy.approval_policy_hash
    ):
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.APPROVAL_POLICY_MISMATCH,),
        )

    binding_map, binding_failure = validate_authority_bindings(
        policy, authority_bindings
    )
    if binding_failure is not None or binding_map is None:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(
                binding_failure or ApprovalFailureCode.AUTHORITY_BINDING_INVALID,
            ),
        )

    normalized, conflict = normalize_decisions(decisions)
    decision_failure = validate_decisions(
        request_id=approval_request_id(request),
        request=request,
        policy=policy,
        bindings=binding_map,
        decisions=normalized,
    )
    if decision_failure is not None:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(decision_failure,),
            normalized_decisions=normalized,
        )

    if conflict:
        return _result(
            request=request,
            policy=policy,
            source_disposition=source.disposition,
            state=ApprovalState.ERROR,
            failures=(ApprovalFailureCode.CONFLICTING_DECISION,),
            normalized_decisions=normalized,
        )

    state = derive_state(policy, normalized)
    return _result(
        request=request,
        policy=policy,
        source_disposition=source.disposition,
        state=state,
        normalized_decisions=normalized,
    )
