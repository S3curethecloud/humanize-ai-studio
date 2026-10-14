from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from app.v3.authority import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssueCode,
    bind_protected_fact,
    derive_presentation,
    validate_protected_fact,
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


def _fact():
    result = bind_protected_fact(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        evidence_family="risks",
        evidence_id="risk-1",
    )
    assert result.value is not None
    return result.value


@pytest.mark.parametrize(
    "replacement_material",
    (
        {
            "title": "Assumption",
            "risk_statement": "Assumption is now fact.",
            "severity": "high",
            "status": "open",
        },
        {
            "title": "Hypothesis",
            "risk_statement": "Hypothesis completed.",
            "severity": "high",
            "status": "resolved",
        },
        {
            "title": "Proposal",
            "risk_statement": "Proposal approved.",
            "severity": "high",
            "status": "approved",
        },
        {
            "title": "Risk",
            "risk_statement": "Risk resolved.",
            "severity": "high",
            "status": "resolved",
        },
        {
            "title": "Evaluation",
            "risk_statement": "Not evaluated became success.",
            "severity": "high",
            "status": "success",
        },
        {
            "title": "Decision",
            "risk_statement": "Architecture decision replaced.",
            "severity": "high",
            "status": "open",
        },
        {
            "title": "Risk",
            "risk_statement": "Caveat removed.",
            "severity": "high",
            "status": "open",
        },
    ),
)
def test_structured_authority_mutation_is_rejected(
    replacement_material: dict[str, str],
) -> None:
    fact = _fact()
    tampered = replace(
        fact,
        material=MappingProxyType(replacement_material),
    )

    result = validate_protected_fact(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        protected_fact=tampered,
    )

    assert result.disposition is AuthorityDisposition.BLOCK
    assert (
        result.issues[0].code
        is AuthorityIssueCode.PROTECTED_FACT_SOURCE_MISMATCH
    )


def test_free_form_assumption_never_becomes_protected_fact() -> None:
    fact = _fact()
    result = derive_presentation(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        source_protected_facts=(fact,),
        presentation_text="Assumption: the risk is resolved.",
    )

    assert result.disposition is AuthorityDisposition.PRESENTATION_ONLY
    assert result.value is not None
    assert result.value.source_fact_ids == (fact.fact_id,)


def test_presentation_text_never_escalates_to_evidence_authority() -> None:
    result = derive_presentation(
        validated_ndeb_result=_validated_result(),
        authority_context=AuthorityContext("tenant-a", "engagement-a"),
        source_protected_facts=(_fact(),),
        presentation_text="This presentation says the risk is approved.",
    )

    assert result.disposition is AuthorityDisposition.PRESENTATION_ONLY
    assert result.disposition is not AuthorityDisposition.ELIGIBLE
