"""Contract tests for Humanize V3.5 governed composition."""

from dataclasses import FrozenInstanceError, fields
from types import MappingProxyType

import pytest

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.composition.contracts import (
    CompositionContentKind,
    CompositionInput,
    CompositionRequest,
)


def _binding(
    *,
    record_id: str = "r1",
    classification: str = "internal",
    tenant_id: str = "tenant-a",
    engagement_id: str | None = "eng-a",
    artifact_ref: str = "artifact://one",
) -> SourceAuthorityBinding:
    cls = MappingProxyType({"level": classification})
    provenance = (MappingProxyType({"provenance_id": f"prov-{record_id}"}),)
    return SourceAuthorityBinding(
        bundle_id="bundle-1",
        evidence_family="facts",
        evidence_id=f"e-{record_id}",
        record_type="fact",
        record_id=record_id,
        record_version=1,
        source_ref=MappingProxyType({"uri": f"source://{record_id}"}),
        provenance_refs=(f"prov-{record_id}",),
        artifact_refs=(artifact_ref,),
        classification=cls,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        material=MappingProxyType({"value": record_id}),
        provenance=provenance,
    )


def _fact(
    binding: SourceAuthorityBinding,
    *,
    fact_id: str | None = None,
) -> ProtectedDeliveryFact:
    return ProtectedDeliveryFact(
        fact_id=fact_id or f"pdf:{binding.record_id}",
        source_binding=binding,
        material=binding.material,
        classification=binding.classification,
        provenance_refs=binding.provenance_refs,
    )


def _presentation(
    binding: SourceAuthorityBinding,
    *,
    derivation_id: str = "presentation:1",
) -> PresentationDerivation:
    return PresentationDerivation(
        derivation_id=derivation_id,
        source_fact_ids=(f"pdf:{binding.record_id}",),
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        classification=binding.classification,
        text="presentation text",
        claim_lock_validation=None,
        authority_disposition=AuthorityDisposition.PRESENTATION_ONLY,
    )

def test_contracts_are_frozen_and_have_no_override_fields() -> None:
    binding = _binding()
    fact = _fact(binding)
    item = CompositionInput(
        input_id="i1",
        position=0,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        source_artifact_ref=binding.artifact_refs[0],
        authority_disposition=AuthorityDisposition.ELIGIBLE,
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        content_kind=CompositionContentKind.PROTECTED_FACT,
        protected_fact=fact,
    )
    request = CompositionRequest(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        inputs=(item,),
        purpose="brief",
    )

    with pytest.raises(FrozenInstanceError):
        item.input_id = "mutated"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        request.purpose = "mutated"  # type: ignore[misc]

    request_fields = {field.name for field in fields(CompositionRequest)}
    prohibited = {
        "truth_override",
        "provenance_override",
        "claim_lock_override",
        "tenant_override",
        "engagement_override",
        "classification_downgrade",
        "protected_fact_promotion",
    }
    assert request_fields.isdisjoint(prohibited)


def test_input_preserves_exact_v34_objects() -> None:
    binding = _binding()
    fact = _fact(binding)
    item = CompositionInput(
        input_id="i1",
        position=3,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        source_artifact_ref=binding.artifact_refs[0],
        authority_disposition=AuthorityDisposition.ELIGIBLE,
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        content_kind=CompositionContentKind.PROTECTED_FACT,
        protected_fact=fact,
    )

    assert item.source_authority_binding is binding
    assert item.protected_fact is fact
    assert item.provenance_binding is binding.provenance
    assert item.classification is binding.classification
