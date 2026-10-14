"""Immutable contracts for Humanize V3.4 authority preservation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.v2.services.claim_lock_validator import ClaimLockValidationResult
from app.v3.ndeb.contracts import JsonValue


class AuthorityDisposition(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    BLOCK = "BLOCK"
    ERROR = "ERROR"
    PRESENTATION_ONLY = "PRESENTATION_ONLY"


class AuthorityIssueCode(StrEnum):
    SOURCE_NOT_VALIDATED = "SOURCE_NOT_VALIDATED"
    SOURCE_BUNDLE_UNAVAILABLE = "SOURCE_BUNDLE_UNAVAILABLE"
    SOURCE_RECORD_UNRESOLVED = "SOURCE_RECORD_UNRESOLVED"
    SOURCE_MANIFEST_UNRESOLVED = "SOURCE_MANIFEST_UNRESOLVED"
    PROVENANCE_UNRESOLVED = "PROVENANCE_UNRESOLVED"
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    ENGAGEMENT_SCOPE_MISMATCH = "ENGAGEMENT_SCOPE_MISMATCH"
    CLASSIFICATION_CHANGE_UNAUTHORIZED = "CLASSIFICATION_CHANGE_UNAUTHORIZED"
    PROTECTED_FACT_SOURCE_MISMATCH = "PROTECTED_FACT_SOURCE_MISMATCH"
    PRESENTATION_AUTHORITY_ESCALATION = "PRESENTATION_AUTHORITY_ESCALATION"
    CLAIM_LOCK_STRICT_VIOLATION = "CLAIM_LOCK_STRICT_VIOLATION"
    CLAIM_LOCK_AUDIT_VIOLATION = "CLAIM_LOCK_AUDIT_VIOLATION"
    CLAIM_LOCK_SEMANTIC_NOT_EVALUATED = "CLAIM_LOCK_SEMANTIC_NOT_EVALUATED"
    UNSUPPORTED_AUTHORITY_TRANSFORMATION = "UNSUPPORTED_AUTHORITY_TRANSFORMATION"


@dataclass(frozen=True, order=True)
class AuthorityIssue:
    code: AuthorityIssueCode
    identifier: str | None = None


@dataclass(frozen=True)
class AuthorityContext:
    tenant_id: str
    engagement_id: str | None

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty")
        if self.engagement_id is not None and not self.engagement_id.strip():
            raise ValueError("engagement_id must be non-empty when provided")


@dataclass(frozen=True)
class SourceAuthorityBinding:
    bundle_id: str
    evidence_family: str
    evidence_id: str
    record_type: str
    record_id: str
    record_version: int
    source_ref: Mapping[str, JsonValue]
    provenance_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    classification: Mapping[str, JsonValue]
    tenant_id: str
    engagement_id: str | None
    material: Mapping[str, JsonValue]
    provenance: tuple[Mapping[str, JsonValue], ...]


@dataclass(frozen=True)
class ProtectedDeliveryFact:
    fact_id: str
    source_binding: SourceAuthorityBinding
    material: Mapping[str, JsonValue]
    classification: Mapping[str, JsonValue]
    provenance_refs: tuple[str, ...]


@dataclass(frozen=True)
class PresentationDerivation:
    derivation_id: str
    source_fact_ids: tuple[str, ...]
    tenant_id: str
    engagement_id: str | None
    classification: Mapping[str, JsonValue]
    text: str
    claim_lock_validation: ClaimLockValidationResult | None
    authority_disposition: AuthorityDisposition = AuthorityDisposition.PRESENTATION_ONLY


@dataclass(frozen=True)
class AuthorityResult[T]:
    disposition: AuthorityDisposition
    value: T | None
    issues: tuple[AuthorityIssue, ...] = ()
