"""Immutable contracts for Humanize V3.6 human approval lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.v3.authority.contracts import AuthorityDisposition


class ApprovalDecisionKind(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUIRE_REVISION = "REQUIRE_REVISION"


class ApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    ERROR = "ERROR"


class ApprovalFailureCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_POLICY = "INVALID_POLICY"
    SOURCE_ERROR = "SOURCE_ERROR"
    SOURCE_BLOCK = "SOURCE_BLOCK"
    SOURCE_COMPOSITION_MISSING = "SOURCE_COMPOSITION_MISSING"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    ENGAGEMENT_MISMATCH = "ENGAGEMENT_MISMATCH"
    STALE_COMPOSITION = "STALE_COMPOSITION"
    APPROVAL_POLICY_MISMATCH = "APPROVAL_POLICY_MISMATCH"
    AUTHORITY_BINDING_INVALID = "AUTHORITY_BINDING_INVALID"
    UNKNOWN_APPROVER = "UNKNOWN_APPROVER"
    UNAUTHORIZED_SCOPE = "UNAUTHORIZED_SCOPE"
    UNAUTHORIZED_DECISION = "UNAUTHORIZED_DECISION"
    APPROVER_AUTHORITY_HASH_MISMATCH = "APPROVER_AUTHORITY_HASH_MISMATCH"
    DECISION_REQUEST_MISMATCH = "DECISION_REQUEST_MISMATCH"
    DECISION_INVALID = "DECISION_INVALID"
    CONFLICTING_DECISION = "CONFLICTING_DECISION"


@dataclass(frozen=True)
class ApprovalRequest:
    tenant_id: str
    engagement_id: str
    composition_id: str
    composition_hash: str
    composition_disposition: AuthorityDisposition
    approval_policy_id: str
    approval_policy_hash: str
    requested_scope: str


@dataclass(frozen=True)
class ApproverAuthorityBinding:
    tenant_id: str
    engagement_id: str
    approver_id: str
    authority_policy_id: str
    authority_policy_hash: str
    allowed_decisions: tuple[ApprovalDecisionKind, ...]
    allowed_requested_scopes: tuple[str, ...]


@dataclass(frozen=True)
class ApprovalPolicy:
    approval_policy_id: str
    approval_policy_hash: str
    required_approver_ids: tuple[str, ...]
    approval_threshold: int


@dataclass(frozen=True)
class ApprovalDecision:
    approval_request_id: str
    approver_id: str
    approver_authority_hash: str
    decision: ApprovalDecisionKind
    reason_code: str
    evidence_hash: str


@dataclass(frozen=True)
class ApprovalResult:
    approval_request_id: str
    composition_id: str
    composition_hash: str
    source_disposition: AuthorityDisposition
    approval_state: ApprovalState
    normalized_decision_ids: tuple[str, ...]
    approval_trace_hash: str
    failure_codes: tuple[ApprovalFailureCode, ...]
