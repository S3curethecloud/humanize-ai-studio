"""Service tests for Humanize V3.5 governed composition."""

from types import MappingProxyType

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.composition import (
    CompositionContentKind,
    CompositionInput,
    CompositionKind,
    CompositionRequest,
    compose,
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

def _fact_input(
    input_id: str,
    position: int,
    *,
    classification: str = "internal",
) -> CompositionInput:
    binding = _binding(
        record_id=input_id,
        classification=classification,
        artifact_ref=f"artifact://{input_id}",
    )
    return CompositionInput(
        input_id=input_id,
        position=position,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        source_artifact_ref=binding.artifact_refs[0],
        authority_disposition=AuthorityDisposition.ELIGIBLE,
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        content_kind=CompositionContentKind.PROTECTED_FACT,
        protected_fact=_fact(binding),
    )


def _presentation_input(input_id: str, position: int) -> CompositionInput:
    binding = _binding(
        record_id=input_id,
        artifact_ref=f"artifact://{input_id}",
    )
    derivation = _presentation(binding, derivation_id=f"presentation:{input_id}")
    return CompositionInput(
        input_id=input_id,
        position=position,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        source_artifact_ref=binding.artifact_refs[0],
        authority_disposition=AuthorityDisposition.PRESENTATION_ONLY,
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        content_kind=CompositionContentKind.PRESENTATION_DERIVATION,
        presentation_derivation=derivation,
    )


def test_authoritative_composition_is_eligible_and_ordered() -> None:
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(_fact_input("b", 2), _fact_input("a", 1)),
            purpose="brief",
        )
    )
    assert decision.disposition is AuthorityDisposition.ELIGIBLE
    assert decision.composition is not None
    assert decision.composition.kind is CompositionKind.AUTHORITATIVE
    assert tuple(e.input_id for e in decision.composition.entries) == ("a", "b")
    assert decision.composition.protected_fact_refs == ("pdf:a", "pdf:b")


def test_all_presentation_composition_stays_presentation_only() -> None:
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(_presentation_input("p", 0),),
            purpose="narrative",
        )
    )
    assert decision.disposition is AuthorityDisposition.PRESENTATION_ONLY
    assert decision.composition is not None
    assert decision.composition.kind is CompositionKind.PRESENTATION
    assert decision.composition.protected_fact_refs == ()
    assert decision.composition.presentation_derivation_refs == ("presentation:p",)


def test_mixed_composition_preserves_distinct_lanes() -> None:
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(_fact_input("f", 0), _presentation_input("p", 1)),
            purpose="mixed",
        )
    )
    assert decision.disposition is AuthorityDisposition.ELIGIBLE
    assert decision.composition is not None
    assert decision.composition.kind is CompositionKind.MIXED
    assert decision.composition.protected_fact_refs == ("pdf:f",)
    assert decision.composition.presentation_derivation_refs == ("presentation:p",)
