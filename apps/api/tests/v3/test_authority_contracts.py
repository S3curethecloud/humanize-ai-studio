from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from app.v3.authority import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssue,
    AuthorityIssueCode,
    bind_protected_fact,
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


def test_authority_disposition_values_are_stable() -> None:
    assert tuple(item.value for item in AuthorityDisposition) == (
        "ELIGIBLE",
        "BLOCK",
        "ERROR",
        "PRESENTATION_ONLY",
    )


def test_authority_context_is_immutable() -> None:
    context = AuthorityContext("tenant-a", "engagement-a")

    with pytest.raises(FrozenInstanceError):
        context.tenant_id = "tenant-b"  # type: ignore[misc]


def test_protected_delivery_fact_identity_is_deterministic() -> None:
    source = _validated_result()
    context = AuthorityContext("tenant-a", "engagement-a")

    first = bind_protected_fact(
        validated_ndeb_result=source,
        authority_context=context,
        evidence_family="risks",
        evidence_id="risk-1",
    )
    second = bind_protected_fact(
        validated_ndeb_result=source,
        authority_context=context,
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert first.disposition is AuthorityDisposition.ELIGIBLE
    assert first.value is not None
    assert second.value is not None
    assert first.value.fact_id == second.value.fact_id
    assert first.value.fact_id.startswith("pdf:sha256:")


def test_source_material_remains_frozen() -> None:
    result = bind_protected_fact(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )

    assert result.value is not None
    with pytest.raises(TypeError):
        result.value.material["status"] = "resolved"  # type: ignore[index]


def test_authority_issue_does_not_carry_arbitrary_source_material() -> None:
    issue = AuthorityIssue(
        code=AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
        identifier="risk-1",
    )

    assert tuple(issue.__dataclass_fields__) == ("code", "identifier")
    assert "A bounded risk remains open." not in repr(issue)
