"""Adversarial fail-closed tests for Humanize V3.5 governed composition."""

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
    CompositionIssueCode,
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

def _input(
    input_id: str,
    position: int,
    *,
    disposition: AuthorityDisposition = AuthorityDisposition.ELIGIBLE,
) -> CompositionInput:
    binding = _binding(record_id=input_id, artifact_ref=f"artifact://{input_id}")
    return CompositionInput(
        input_id=input_id,
        position=position,
        tenant_id=binding.tenant_id,
        engagement_id=binding.engagement_id,
        source_artifact_ref=binding.artifact_refs[0],
        authority_disposition=disposition,
        source_authority_binding=binding,
        provenance_binding=binding.provenance,
        classification=binding.classification,
        content_kind=CompositionContentKind.PROTECTED_FACT,
        protected_fact=_fact(binding),
    )


def test_duplicate_position_returns_error_without_composition() -> None:
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(_input("a", 1), _input("b", 1)),
            purpose="brief",
        )
    )
    assert decision.disposition is AuthorityDisposition.ERROR
    assert decision.composition is None
    assert CompositionIssueCode.DUPLICATE_POSITION in {
        issue.code for issue in decision.issues
    }


def test_incoming_error_has_precedence_over_incoming_block() -> None:
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(
                _input("block", 1, disposition=AuthorityDisposition.BLOCK),
                _input("error", 2, disposition=AuthorityDisposition.ERROR),
            ),
            purpose="brief",
        )
    )
    assert decision.disposition is AuthorityDisposition.ERROR
    assert decision.composition is None
    assert decision.issues[0].code is CompositionIssueCode.INCOMING_ERROR


def test_requested_classification_change_blocks() -> None:
    item = _input("a", 0)
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(item,),
            purpose="brief",
            requested_output_classification={"level": "public"},
        )
    )
    assert decision.disposition is AuthorityDisposition.BLOCK
    assert decision.composition is None
    assert decision.issues[0].code is (
        CompositionIssueCode.CLASSIFICATION_CHANGE_UNAUTHORIZED
    )


def test_missing_source_artifact_reference_errors() -> None:
    item = _input("a", 0)
    malformed = CompositionInput(
        input_id=item.input_id,
        position=item.position,
        tenant_id=item.tenant_id,
        engagement_id=item.engagement_id,
        source_artifact_ref="artifact://missing",
        authority_disposition=item.authority_disposition,
        source_authority_binding=item.source_authority_binding,
        provenance_binding=item.provenance_binding,
        classification=item.classification,
        content_kind=item.content_kind,
        protected_fact=item.protected_fact,
    )
    decision = compose(
        CompositionRequest(
            tenant_id="tenant-a",
            engagement_id="eng-a",
            inputs=(malformed,),
            purpose="brief",
        )
    )
    assert decision.disposition is AuthorityDisposition.ERROR
    assert decision.composition is None
