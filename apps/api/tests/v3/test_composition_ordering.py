"""Ordering tests for Humanize V3.5 governed composition."""

from types import MappingProxyType

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.composition.contracts import (
    CompositionContentKind,
    CompositionInput,
    CompositionIssueCode,
)
from app.v3.composition.ordering import order_inputs


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

def _item(input_id: str, position: int) -> CompositionInput:
    binding = _binding(record_id=input_id, artifact_ref=f"artifact://{input_id}")
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


def test_explicit_positions_override_caller_order() -> None:
    second = _item("second", 20)
    first = _item("first", 10)
    ordered, issues = order_inputs((second, first))
    assert issues == ()
    assert tuple(item.input_id for item in ordered) == ("first", "second")


def test_duplicate_positions_fail_closed() -> None:
    ordered, issues = order_inputs((_item("a", 1), _item("b", 1)))
    assert ordered == ()
    assert tuple(issue.code for issue in issues) == (
        CompositionIssueCode.DUPLICATE_POSITION,
    )


def test_duplicate_ids_and_negative_positions_fail_closed() -> None:
    ordered, issues = order_inputs((_item("a", -1), _item("a", 2)))
    assert ordered == ()
    assert {issue.code for issue in issues} == {
        CompositionIssueCode.INVALID_POSITION,
        CompositionIssueCode.DUPLICATE_INPUT_ID,
    }
