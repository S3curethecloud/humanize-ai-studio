"""Immutable contracts for Humanize V3.5 governed composition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.ndeb.contracts import JsonValue


class CompositionContentKind(StrEnum):
    PROTECTED_FACT = "PROTECTED_FACT"
    PRESENTATION_DERIVATION = "PRESENTATION_DERIVATION"


class CompositionKind(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    PRESENTATION = "PRESENTATION"
    MIXED = "MIXED"


class CompositionIssueCode(StrEnum):
    EMPTY_INPUT_SET = "EMPTY_INPUT_SET"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_INPUT = "INVALID_INPUT"
    DUPLICATE_INPUT_ID = "DUPLICATE_INPUT_ID"
    INVALID_POSITION = "INVALID_POSITION"
    DUPLICATE_POSITION = "DUPLICATE_POSITION"
    SOURCE_ARTIFACT_UNRESOLVED = "SOURCE_ARTIFACT_UNRESOLVED"
    SOURCE_AUTHORITY_MISMATCH = "SOURCE_AUTHORITY_MISMATCH"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    CONTENT_REFERENCE_INVALID = "CONTENT_REFERENCE_INVALID"
    CONTENT_AUTHORITY_MISMATCH = "CONTENT_AUTHORITY_MISMATCH"
    INCOMING_ERROR = "INCOMING_ERROR"
    INCOMING_BLOCK = "INCOMING_BLOCK"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    ENGAGEMENT_MISMATCH = "ENGAGEMENT_MISMATCH"
    CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"
    CLASSIFICATION_CHANGE_UNAUTHORIZED = "CLASSIFICATION_CHANGE_UNAUTHORIZED"
    PROTECTED_FACT_CONFLICT = "PROTECTED_FACT_CONFLICT"


@dataclass(frozen=True, order=True)
class CompositionIssue:
    code: CompositionIssueCode
    input_id: str | None = None


@dataclass(frozen=True)
class CompositionInput:
    input_id: str
    position: int
    tenant_id: str
    engagement_id: str | None
    source_artifact_ref: str
    authority_disposition: AuthorityDisposition
    source_authority_binding: SourceAuthorityBinding
    provenance_binding: tuple[Mapping[str, JsonValue], ...]
    classification: Mapping[str, JsonValue]
    content_kind: CompositionContentKind
    protected_fact: ProtectedDeliveryFact | None = None
    presentation_derivation: PresentationDerivation | None = None
    claim_lock_evidence_ref: str | None = None


@dataclass(frozen=True)
class CompositionRequest:
    tenant_id: str
    engagement_id: str | None
    inputs: tuple[CompositionInput, ...]
    purpose: str
    requested_output_classification: Mapping[str, JsonValue] | None = None


@dataclass(frozen=True)
class GovernedCompositionEntry:
    input_id: str
    position: int
    content_kind: CompositionContentKind
    source_artifact_ref: str
    source_authority_binding: SourceAuthorityBinding
    provenance_binding: tuple[Mapping[str, JsonValue], ...]
    classification: Mapping[str, JsonValue]
    protected_fact: ProtectedDeliveryFact | None
    presentation_derivation: PresentationDerivation | None
    authority_disposition: AuthorityDisposition
    claim_lock_evidence_ref: str | None


@dataclass(frozen=True)
class CompositionInputEvidence:
    input_id: str
    position: int
    content_kind: CompositionContentKind
    authority_disposition: AuthorityDisposition
    source_artifact_ref: str
    source_authority_identity: str
    provenance_identity: str
    classification_identity: str
    content_reference_id: str


@dataclass(frozen=True)
class CompositionEvidence:
    ordered_input_ids: tuple[str, ...]
    input_evidence: tuple[CompositionInputEvidence, ...]
    issues: tuple[CompositionIssue, ...]


@dataclass(frozen=True)
class GovernedComposition:
    composition_id: str
    tenant_id: str
    engagement_id: str | None
    entries: tuple[GovernedCompositionEntry, ...]
    aggregate_classification: Mapping[str, JsonValue] | None
    provenance_ledger: tuple[tuple[Mapping[str, JsonValue], ...], ...]
    source_authority_ledger: tuple[SourceAuthorityBinding, ...]
    protected_fact_refs: tuple[str, ...]
    presentation_derivation_refs: tuple[str, ...]
    kind: CompositionKind
    disposition: AuthorityDisposition
    evidence: CompositionEvidence


@dataclass(frozen=True)
class CompositionDecision:
    disposition: AuthorityDisposition
    composition: GovernedComposition | None
    issues: tuple[CompositionIssue, ...]
    evidence: CompositionEvidence
