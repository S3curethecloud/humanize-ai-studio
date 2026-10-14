from __future__ import annotations

from types import MappingProxyType

from app.v3.authority import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssueCode,
    bind_source_authority,
)
from app.v3.ndeb.contracts import NdebDisposition, NdebValidationResult


def _source_ref(name: str):
    return MappingProxyType(
        {"object_type": "record", "object_id": name, "object_version": 1}
    )


def _classification(label: str = "internal"):
    return MappingProxyType(
        {
            "value": label,
            "authority_ref": _source_ref("classification-policy"),
        }
    )


def _validated_result(
    *,
    tenant_id: str = "tenant-a",
    engagement_id: str = "engagement-a",
    evidence_id: str = "risk-1",
    classification=None,
    manifest_classification=None,
    provenance_refs: tuple[str, ...] = ("prov-1",),
    provenance_entries=None,
    material=None,
):
    selected_classification = classification or _classification()
    selected_manifest_classification = (
        manifest_classification or selected_classification
    )
    selected_material = material or MappingProxyType(
        {
            "title": "Risk",
            "risk_statement": "A bounded risk remains open.",
            "severity": "high",
            "status": "open",
        }
    )
    source = _source_ref("risk-source")
    record = MappingProxyType(
        {
            "evidence_id": evidence_id,
            "record_type": "risk",
            "record_id": "record-1",
            "record_version": 1,
            "source_ref": source,
            "classification": selected_classification,
            "provenance_refs": provenance_refs,
            "artifact_refs": (),
            "material": selected_material,
        }
    )
    manifest = MappingProxyType(
        {
            "evidence_id": evidence_id,
            "evidence_family": "risks",
            "record_ref": source,
            "classification": selected_manifest_classification,
            "provenance_refs": provenance_refs,
            "artifact_refs": (),
        }
    )
    if provenance_entries is None:
        provenance_entries = (
            MappingProxyType(
                {
                    "provenance_id": "prov-1",
                    "subject_ref": MappingProxyType(
                        {"subject_type": "evidence", "subject_id": evidence_id}
                    ),
                    "source_refs": (source,),
                    "recorded_at": "2026-01-01T00:00:00Z",
                }
            ),
        )
    evidence = MappingProxyType({"risks": (record,)})
    bundle = MappingProxyType(
        {
            "bundle_id": "ndeb:sha256:" + "1" * 64,
            "tenant_id": tenant_id,
            "engagement_id": engagement_id,
            "evidence": evidence,
            "evidence_manifest": (manifest,),
            "provenance": provenance_entries,
        }
    )
    return NdebValidationResult(
        disposition=NdebDisposition.VALIDATED,
        issues=(),
        validated_bundle=bundle,
        computed_digest_sha256="1" * 64,
    )


def test_validated_v3_3_source_binds_successfully() -> None:
    result = bind_source_authority(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.ELIGIBLE
    assert result.value is not None
    assert result.value.tenant_id == "tenant-a"
    assert result.value.provenance_refs == ("prov-1",)


def test_nonvalidated_source_cannot_bind() -> None:
    source = NdebValidationResult(
        disposition=NdebDisposition.REJECTED,
        issues=(),
        validated_bundle=None,
        computed_digest_sha256=None,
    )

    result = bind_source_authority(
        validated_ndeb_result=source,
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.ERROR
    assert result.issues[0].code is AuthorityIssueCode.SOURCE_NOT_VALIDATED


def test_missing_validated_bundle_is_error() -> None:
    source = NdebValidationResult(
        disposition=NdebDisposition.VALIDATED,
        issues=(),
        validated_bundle=None,
        computed_digest_sha256=None,
    )

    result = bind_source_authority(
        validated_ndeb_result=source,
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.ERROR
    assert result.issues[0].code is AuthorityIssueCode.SOURCE_BUNDLE_UNAVAILABLE


def test_manifest_classification_value_drift_fails_closed() -> None:
    result = bind_source_authority(
        validated_ndeb_result=_validated_result(
            manifest_classification=_classification("confidential")
        ),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.ERROR
    assert result.issues[0].code is AuthorityIssueCode.SOURCE_MANIFEST_UNRESOLVED


def test_manifest_classification_authority_drift_fails_closed() -> None:
    changed = MappingProxyType(
        {
            "value": "internal",
            "authority_ref": _source_ref("different-classification-policy"),
        }
    )
    result = bind_source_authority(
        validated_ndeb_result=_validated_result(
            manifest_classification=changed
        ),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.ERROR
    assert result.issues[0].code is AuthorityIssueCode.SOURCE_MANIFEST_UNRESOLVED


def test_dangling_provenance_fails_closed() -> None:
    result = bind_source_authority(
        validated_ndeb_result=_validated_result(
            provenance_refs=("missing-prov",),
            provenance_entries=(),
        ),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.ERROR
    assert result.issues[0].code is AuthorityIssueCode.PROVENANCE_UNRESOLVED


def test_engagement_mismatch_blocks() -> None:
    result = bind_source_authority(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-b"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.BLOCK
    assert result.issues[0].code is AuthorityIssueCode.ENGAGEMENT_SCOPE_MISMATCH
