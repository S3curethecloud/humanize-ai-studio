"""Conflict tests for Humanize V3.5 governed composition."""

from types import MappingProxyType

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.composition.conflicts import (
    authoritative_classification,
    detect_protected_fact_conflicts,
)
from app.v3.composition.contracts import (
    CompositionContentKind,
    CompositionInput,
    CompositionIssueCode,
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

def _item(
    input_id: str,
    binding: SourceAuthorityBinding,
    *,
    fact: ProtectedDeliveryFact | None = None,
) -> CompositionInput:
    return CompositionInput(
        input_id=input_id,
        position=0 if input_id == "a" else 1,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        source_artifact_ref=binding.artifact_refs[0],
        authority_disposition=AuthorityDisposition.ELIGIBLE,
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        content_kind=CompositionContentKind.PROTECTED_FACT,
        protected_fact=fact or _fact(binding),
    )


def test_exact_duplicate_binding_surface_is_not_a_conflict() -> None:
    binding = _binding()
    fact = _fact(binding, fact_id="pdf:same")
    assert detect_protected_fact_conflicts(
        (_item("a", binding, fact=fact), _item("b", binding, fact=fact))
    ) == ()


def test_same_binding_key_with_different_fact_identity_blocks() -> None:
    binding = _binding()
    issues = detect_protected_fact_conflicts(
        (
            _item("a", binding, fact=_fact(binding, fact_id="pdf:a")),
            _item("b", binding, fact=_fact(binding, fact_id="pdf:b")),
        )
    )
    assert tuple(issue.code for issue in issues) == (
        CompositionIssueCode.PROTECTED_FACT_CONFLICT,
    )


def test_unequal_authoritative_classification_blocks() -> None:
    left = _binding(record_id="left", classification="internal")
    right = _binding(record_id="right", classification="restricted")
    classification, issues = authoritative_classification(
        (_item("a", left), _item("b", right))
    )
    assert classification is None
    assert tuple(issue.code for issue in issues) == (
        CompositionIssueCode.CLASSIFICATION_CONFLICT,
    )


def test_same_binding_key_with_changed_provenance_blocks() -> None:
    binding = _binding()
    altered = SourceAuthorityBinding(
        bundle_id=binding.bundle_id,
        evidence_family=binding.evidence_family,
        evidence_id=binding.evidence_id,
        record_type=binding.record_type,
        record_id=binding.record_id,
        record_version=binding.record_version,
        source_ref=binding.source_ref,
        provenance_refs=("other",),
        artifact_refs=binding.artifact_refs,
        classification=binding.classification,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        material=binding.material,
        provenance=(MappingProxyType({"provenance_id": "other"}),),
    )
    issues = detect_protected_fact_conflicts(
        (_item("a", binding), _item("b", altered))
    )
    assert tuple(issue.code for issue in issues) == (
        CompositionIssueCode.PROTECTED_FACT_CONFLICT,
    )
