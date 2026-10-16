"""Identity tests for Humanize V3.5 governed composition."""

from types import MappingProxyType

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.composition.contracts import (
    CompositionContentKind,
    GovernedCompositionEntry,
)
from app.v3.composition.identity import composition_identity


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

def _entry(input_id: str, position: int) -> GovernedCompositionEntry:
    binding = _binding(record_id=input_id, artifact_ref=f"artifact://{input_id}")
    fact = _fact(binding)
    return GovernedCompositionEntry(
        input_id=input_id,
        position=position,
        content_kind=CompositionContentKind.PROTECTED_FACT,
        source_artifact_ref=binding.artifact_refs[0],
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        protected_fact=fact,
        presentation_derivation=None,
        authority_disposition=AuthorityDisposition.ELIGIBLE,
        claim_lock_evidence_ref=None,
    )


def test_identity_is_deterministic_for_same_surface() -> None:
    entries = (_entry("a", 0), _entry("b", 1))
    first = composition_identity(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        purpose="brief",
        entries=entries,
        aggregate_classification=entries[0].classification,
    )
    second = composition_identity(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        purpose="brief",
        entries=entries,
        aggregate_classification=entries[0].classification,
    )
    assert first == second
    assert first.startswith("composition:sha256:")


def test_identity_changes_when_explicit_order_changes() -> None:
    first_entries = (_entry("a", 0), _entry("b", 1))
    second_entries = (_entry("a", 1), _entry("b", 0))
    first = composition_identity(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        purpose="brief",
        entries=first_entries,
        aggregate_classification=first_entries[0].classification,
    )
    second = composition_identity(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        purpose="brief",
        entries=second_entries,
        aggregate_classification=second_entries[0].classification,
    )
    assert first != second


def test_identity_changes_with_purpose() -> None:
    entries = (_entry("a", 0),)
    one = composition_identity(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        purpose="brief",
        entries=entries,
        aggregate_classification=entries[0].classification,
    )
    two = composition_identity(
        tenant_id="tenant-a",
        engagement_id="eng-a",
        purpose="report",
        entries=entries,
        aggregate_classification=entries[0].classification,
    )
    assert one != two
