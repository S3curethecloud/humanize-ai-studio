"""Canonical deterministic identities for Humanize V3.6 approval."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from enum import Enum

from .contracts import (
    ApprovalDecision,
    ApprovalFailureCode,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalState,
    ApproverAuthorityBinding,
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_COMPOSITION_ID = re.compile(r"^composition:sha256:([0-9a-f]{64})$")


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [_jsonable(child) for child in value]
    raise TypeError(f"unsupported approval identity value: {type(value)!r}")


def _digest(value: object) -> str:
    encoded = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and _SHA256_HEX.fullmatch(value) is not None


def composition_hash_from_id(composition_id: object) -> str | None:
    if not isinstance(composition_id, str):
        return None
    match = _COMPOSITION_ID.fullmatch(composition_id)
    return match.group(1) if match is not None else None


def approval_policy_hash(
    approval_policy_id: str,
    required_approver_ids: tuple[str, ...],
    approval_threshold: int,
) -> str:
    return _digest(
        {
            "schema": "humanize-v3.6-approval-policy-r1",
            "approval_policy_id": approval_policy_id,
            "required_approver_ids": required_approver_ids,
            "approval_threshold": approval_threshold,
        }
    )


def approval_request_id(request: ApprovalRequest) -> str:
    return _digest(
        {
            "schema": "humanize-v3.6-approval-request-r1",
            "tenant_id": request.tenant_id,
            "engagement_id": request.engagement_id,
            "composition_id": request.composition_id,
            "composition_hash": request.composition_hash,
            "source_disposition": request.composition_disposition,
            "approval_policy_id": request.approval_policy_id,
            "approval_policy_hash": request.approval_policy_hash,
            "requested_scope": request.requested_scope,
        }
    )


def approver_authority_hash(binding: ApproverAuthorityBinding) -> str:
    return _digest(
        {
            "schema": "humanize-v3.6-approver-authority-r1",
            "tenant_id": binding.tenant_id,
            "engagement_id": binding.engagement_id,
            "approver_id": binding.approver_id,
            "authority_policy_id": binding.authority_policy_id,
            "authority_policy_hash": binding.authority_policy_hash,
            "allowed_decisions": tuple(
                sorted(decision.value for decision in binding.allowed_decisions)
            ),
            "allowed_requested_scopes": tuple(
                sorted(binding.allowed_requested_scopes)
            ),
        }
    )


def approval_decision_id(decision: ApprovalDecision) -> str:
    return _digest(
        {
            "schema": "humanize-v3.6-approval-decision-r1",
            "approval_request_id": decision.approval_request_id,
            "approver_id": decision.approver_id,
            "approver_authority_hash": decision.approver_authority_hash,
            "decision": decision.decision,
            "reason_code": decision.reason_code,
            "evidence_hash": decision.evidence_hash,
        }
    )


def approval_trace_hash(
    *,
    approval_request_id_value: str,
    policy: ApprovalPolicy,
    normalized_decisions: tuple[ApprovalDecision, ...],
    final_state: ApprovalState,
    failure_codes: tuple[ApprovalFailureCode, ...],
) -> str:
    decision_surface = tuple(
        {
            "approver_id": decision.approver_id,
            "approval_decision_id": approval_decision_id(decision),
        }
        for decision in normalized_decisions
    )
    return _digest(
        {
            "schema": "humanize-v3.6-approval-trace-r1",
            "approval_request_id": approval_request_id_value,
            "approval_policy_id": policy.approval_policy_id,
            "approval_policy_hash": policy.approval_policy_hash,
            "normalized_decisions": decision_surface,
            "final_state": final_state,
            "failure_codes": tuple(
                sorted(code.value for code in failure_codes)
            ),
        }
    )
