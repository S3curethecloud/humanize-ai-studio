"""Canonical internal identity for Humanize V3.5 governed composition."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import Enum

from app.v3.authority.contracts import SourceAuthorityBinding
from app.v3.ndeb.contracts import JsonValue

from .contracts import GovernedCompositionEntry


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
    raise TypeError(f"unsupported composition identity value: {type(value)!r}")


def _digest(value: object) -> str:
    encoded = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_authority_identity(binding: SourceAuthorityBinding) -> str:
    return "authority:sha256:" + _digest(
        {
            "bundle_id": binding.bundle_id,
            "evidence_family": binding.evidence_family,
            "evidence_id": binding.evidence_id,
            "record_type": binding.record_type,
            "record_id": binding.record_id,
            "record_version": binding.record_version,
            "source_ref": binding.source_ref,
            "provenance_refs": binding.provenance_refs,
            "artifact_refs": binding.artifact_refs,
            "classification": binding.classification,
            "tenant_id": binding.tenant_id,
            "engagement_id": binding.engagement_id,
            "material": binding.material,
            "provenance": binding.provenance,
        }
    )


def provenance_identity(
    provenance: tuple[Mapping[str, JsonValue], ...],
) -> str:
    return "provenance:sha256:" + _digest(provenance)


def classification_identity(classification: Mapping[str, JsonValue]) -> str:
    return "classification:sha256:" + _digest(classification)


def content_reference_id(entry: GovernedCompositionEntry) -> str:
    if entry.protected_fact is not None:
        return entry.protected_fact.fact_id
    if entry.presentation_derivation is not None:
        return entry.presentation_derivation.derivation_id
    raise ValueError("composition entry has no content reference")


def entry_identity_surface(entry: GovernedCompositionEntry) -> Mapping[str, object]:
    return {
        "input_id": entry.input_id,
        "position": entry.position,
        "content_kind": entry.content_kind.value,
        "source_artifact_ref": entry.source_artifact_ref,
        "source_authority_identity": source_authority_identity(
            entry.source_authority_binding
        ),
        "provenance_identity": provenance_identity(entry.provenance_binding),
        "classification": entry.classification,
        "content_reference_id": content_reference_id(entry),
        "authority_disposition": entry.authority_disposition.value,
        "claim_lock_evidence_ref": entry.claim_lock_evidence_ref,
    }


def composition_identity(
    *,
    tenant_id: str,
    engagement_id: str | None,
    purpose: str,
    entries: tuple[GovernedCompositionEntry, ...],
    aggregate_classification: Mapping[str, JsonValue] | None,
) -> str:
    return "composition:sha256:" + _digest(
        {
            "schema": "humanize-v3.5-governed-composition-r1",
            "tenant_id": tenant_id,
            "engagement_id": engagement_id,
            "purpose": purpose,
            "entries": tuple(entry_identity_surface(entry) for entry in entries),
            "aggregate_classification": aggregate_classification,
        }
    )
