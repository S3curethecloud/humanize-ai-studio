from __future__ import annotations

from types import MappingProxyType

from app.v3.authority import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssueCode,
    bind_protected_fact,
    derive_presentation,
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


def test_foreign_tenant_source_binding_blocks() -> None:
    result = bind_protected_fact(
        validated_ndeb_result=_validated_result(tenant_id="tenant-b"),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.BLOCK
    assert result.issues[0].code is AuthorityIssueCode.TENANT_SCOPE_MISMATCH


def test_foreign_engagement_source_binding_blocks() -> None:
    result = bind_protected_fact(
        validated_ndeb_result=_validated_result(engagement_id="engagement-b"),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.disposition is AuthorityDisposition.BLOCK
    assert result.issues[0].code is AuthorityIssueCode.ENGAGEMENT_SCOPE_MISMATCH


def test_same_evidence_id_across_tenants_does_not_authorize_reuse() -> None:
    foreign = bind_protected_fact(
        validated_ndeb_result=_validated_result(tenant_id="tenant-b"),
        authority_context=AuthorityContext("tenant-b", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )
    assert foreign.value is not None

    result = derive_presentation(
        validated_ndeb_result=_validated_result(tenant_id="tenant-a"),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        source_protected_facts=(foreign.value,),
        presentation_text="Matching text does not transfer authority.",
    )

    assert result.disposition is AuthorityDisposition.BLOCK
    assert (
        result.issues[0].code
        is AuthorityIssueCode.PROTECTED_FACT_SOURCE_MISMATCH
    )


def test_matching_text_across_tenants_does_not_authorize_reuse() -> None:
    common_material = MappingProxyType(
        {
            "title": "Risk",
            "risk_statement": "Identical text.",
            "severity": "high",
            "status": "open",
        }
    )
    foreign_source = _validated_result(
        tenant_id="tenant-b",
        material=common_material,
    )
    foreign = bind_protected_fact(
        validated_ndeb_result=foreign_source,
        authority_context=AuthorityContext("tenant-b", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )
    assert foreign.value is not None

    result = derive_presentation(
        validated_ndeb_result=_validated_result(
            tenant_id="tenant-a",
            material=common_material,
        ),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        source_protected_facts=(foreign.value,),
        presentation_text="Identical text.",
    )

    assert result.disposition is AuthorityDisposition.BLOCK


def test_foreign_fact_cannot_participate_in_derivation() -> None:
    foreign = bind_protected_fact(
        validated_ndeb_result=_validated_result(
            tenant_id="tenant-b",
            engagement_id="engagement-b",
        ),
        authority_context=AuthorityContext("tenant-b", "engagement-b"),
        evidence_family="risks",
        evidence_id="risk-1",
    )
    assert foreign.value is not None

    result = derive_presentation(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        source_protected_facts=(foreign.value,),
        presentation_text="Foreign authority must fail closed.",
    )

    assert result.disposition is AuthorityDisposition.BLOCK
