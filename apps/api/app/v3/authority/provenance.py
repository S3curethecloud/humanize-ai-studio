"""Source-authority and provenance binding for Humanize V3.4."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import cast

from app.v3.ndeb.contracts import (
    JsonValue,
    NdebDisposition,
    NdebValidationResult,
)

from .contracts import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssue,
    AuthorityIssueCode,
    AuthorityResult,
    SourceAuthorityBinding,
)


def _freeze_json(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        source = cast(Mapping[object, object], value)
        frozen: dict[str, JsonValue] = {}
        for key, child in source.items():
            if not isinstance(key, str):
                raise TypeError("JSON object key must be a string")
            frozen[key] = _freeze_json(child)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        return tuple(_freeze_json(child) for child in sequence)
    raise TypeError("unsupported authority JSON value")


def _mapping(value: object) -> Mapping[str, JsonValue] | None:
    if not isinstance(value, Mapping):
        return None
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):
        return None
    return frozen


def _string_tuple(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    items = tuple(value)
    if not all(isinstance(item, str) for item in items):
        return None
    return cast(tuple[str, ...], items)


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, JsonValue], ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    output: list[Mapping[str, JsonValue]] = []
    for item in value:
        mapping = _mapping(item)
        if mapping is None:
            return None
        output.append(mapping)
    return tuple(output)


def _result(
    disposition: AuthorityDisposition,
    code: AuthorityIssueCode,
    identifier: str | None = None,
) -> AuthorityResult[SourceAuthorityBinding]:
    return AuthorityResult(
        disposition=disposition,
        value=None,
        issues=(AuthorityIssue(code=code, identifier=identifier),),
    )


def bind_source_authority(
    *,
    validated_ndeb_result: NdebValidationResult,
    authority_context: AuthorityContext,
    evidence_family: str,
    evidence_id: str,
) -> AuthorityResult[SourceAuthorityBinding]:
    if validated_ndeb_result.disposition is not NdebDisposition.VALIDATED:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_NOT_VALIDATED,
        )

    bundle = validated_ndeb_result.validated_bundle
    if bundle is None:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_BUNDLE_UNAVAILABLE,
        )

    bundle_id = bundle.get("bundle_id")
    source_tenant_id = bundle.get("tenant_id")
    source_engagement_id = bundle.get("engagement_id")

    if not isinstance(bundle_id, str) or not isinstance(source_tenant_id, str):
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_BUNDLE_UNAVAILABLE,
        )
    if source_engagement_id is not None and not isinstance(source_engagement_id, str):
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_BUNDLE_UNAVAILABLE,
        )

    if authority_context.tenant_id != source_tenant_id:
        return _result(
            AuthorityDisposition.BLOCK,
            AuthorityIssueCode.TENANT_SCOPE_MISMATCH,
            evidence_id,
        )
    if (
        source_engagement_id is not None
        and authority_context.engagement_id != source_engagement_id
    ):
        return _result(
            AuthorityDisposition.BLOCK,
            AuthorityIssueCode.ENGAGEMENT_SCOPE_MISMATCH,
            evidence_id,
        )

    evidence_root = _mapping(bundle.get("evidence"))
    if evidence_root is None:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
            evidence_id,
        )

    family_items = _sequence_of_mappings(evidence_root.get(evidence_family))
    if family_items is None:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
            evidence_id,
        )

    matches = tuple(
        item for item in family_items if item.get("evidence_id") == evidence_id
    )
    if len(matches) != 1:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
            evidence_id,
        )
    record = matches[0]

    manifest_entries = _sequence_of_mappings(bundle.get("evidence_manifest"))
    if manifest_entries is None:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_MANIFEST_UNRESOLVED,
            evidence_id,
        )
    manifest_matches = tuple(
        entry for entry in manifest_entries if entry.get("evidence_id") == evidence_id
    )
    if len(manifest_matches) != 1:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_MANIFEST_UNRESOLVED,
            evidence_id,
        )
    manifest = manifest_matches[0]

    source_ref = _mapping(record.get("source_ref"))
    classification = _mapping(record.get("classification"))
    material = _mapping(record.get("material"))
    provenance_refs = _string_tuple(record.get("provenance_refs"))
    artifact_refs = _string_tuple(record.get("artifact_refs"))

    record_type = record.get("record_type")
    record_id = record.get("record_id")
    record_version = record.get("record_version")

    if (
        source_ref is None
        or classification is None
        or material is None
        or provenance_refs is None
        or artifact_refs is None
        or not isinstance(record_type, str)
        or not isinstance(record_id, str)
        or not isinstance(record_version, int)
        or isinstance(record_version, bool)
    ):
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
            evidence_id,
        )

    manifest_provenance_refs = _string_tuple(manifest.get("provenance_refs"))
    manifest_artifact_refs = _string_tuple(manifest.get("artifact_refs"))
    manifest_record_ref = _mapping(manifest.get("record_ref"))
    manifest_classification = _mapping(manifest.get("classification"))

    if (
        manifest.get("evidence_family") != evidence_family
        or manifest_record_ref != source_ref
        or manifest_classification != classification
        or manifest_provenance_refs != provenance_refs
        or manifest_artifact_refs != artifact_refs
    ):
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.SOURCE_MANIFEST_UNRESOLVED,
            evidence_id,
        )

    provenance_entries = _sequence_of_mappings(bundle.get("provenance"))
    if provenance_entries is None:
        return _result(
            AuthorityDisposition.ERROR,
            AuthorityIssueCode.PROVENANCE_UNRESOLVED,
            evidence_id,
        )

    resolved: list[Mapping[str, JsonValue]] = []
    for provenance_id in provenance_refs:
        provenance_matches = tuple(
            entry
            for entry in provenance_entries
            if entry.get("provenance_id") == provenance_id
        )
        if len(provenance_matches) != 1:
            return _result(
                AuthorityDisposition.ERROR,
                AuthorityIssueCode.PROVENANCE_UNRESOLVED,
                provenance_id,
            )
        resolved.append(provenance_matches[0])

    binding = SourceAuthorityBinding(
        bundle_id=bundle_id,
        evidence_family=evidence_family,
        evidence_id=evidence_id,
        record_type=record_type,
        record_id=record_id,
        record_version=record_version,
        source_ref=source_ref,
        provenance_refs=provenance_refs,
        artifact_refs=artifact_refs,
        classification=classification,
        tenant_id=source_tenant_id,
        engagement_id=source_engagement_id,
        material=material,
        provenance=tuple(resolved),
    )

    return AuthorityResult(
        disposition=AuthorityDisposition.ELIGIBLE,
        value=binding,
    )
