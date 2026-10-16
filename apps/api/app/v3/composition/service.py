"""Deterministic provider-free Humanize V3.5 composition service."""

from __future__ import annotations

from collections.abc import Mapping

from app.v3.authority.contracts import (
    AuthorityDisposition,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from app.v3.ndeb.contracts import JsonValue

from .conflicts import authoritative_classification, detect_protected_fact_conflicts
from .contracts import (
    CompositionContentKind,
    CompositionDecision,
    CompositionEvidence,
    CompositionInput,
    CompositionInputEvidence,
    CompositionIssue,
    CompositionIssueCode,
    CompositionKind,
    CompositionRequest,
    GovernedComposition,
    GovernedCompositionEntry,
)
from .identity import (
    classification_identity,
    composition_identity,
    provenance_identity,
    source_authority_identity,
)
from .ordering import order_inputs


def _evidence(
    inputs: tuple[CompositionInput, ...],
    issues: tuple[CompositionIssue, ...],
) -> CompositionEvidence:
    records: list[CompositionInputEvidence] = []
    for item in inputs:
        if (
            isinstance(item.source_authority_binding, SourceAuthorityBinding)
            and isinstance(item.classification, Mapping)
            and isinstance(item.provenance_binding, tuple)
        ):
            if item.protected_fact is not None:
                ref = item.protected_fact.fact_id
            elif item.presentation_derivation is not None:
                ref = item.presentation_derivation.derivation_id
            else:
                ref = ""
            records.append(
                CompositionInputEvidence(
                    input_id=item.input_id,
                    position=item.position,
                    content_kind=item.content_kind,
                    authority_disposition=item.authority_disposition,
                    source_artifact_ref=item.source_artifact_ref,
                    source_authority_identity=source_authority_identity(
                        item.source_authority_binding
                    ),
                    provenance_identity=provenance_identity(
                        item.provenance_binding
                    ),
                    classification_identity=classification_identity(
                        item.classification
                    ),
                    content_reference_id=ref,
                )
            )
    return CompositionEvidence(
        ordered_input_ids=tuple(item.input_id for item in inputs),
        input_evidence=tuple(records),
        issues=issues,
    )


def _decision(
    disposition: AuthorityDisposition,
    *,
    inputs: tuple[CompositionInput, ...],
    issues: tuple[CompositionIssue, ...],
) -> CompositionDecision:
    return CompositionDecision(
        disposition=disposition,
        composition=None,
        issues=issues,
        evidence=_evidence(inputs, issues),
    )


def _structural_issues(
    request: CompositionRequest,
    ordered: tuple[CompositionInput, ...],
) -> tuple[CompositionIssue, ...]:
    issues: list[CompositionIssue] = []

    if not isinstance(request.tenant_id, str) or not request.tenant_id.strip():
        issues.append(CompositionIssue(code=CompositionIssueCode.INVALID_REQUEST))
    if (
        request.engagement_id is not None
        and (
            not isinstance(request.engagement_id, str)
            or not request.engagement_id.strip()
        )
    ):
        issues.append(CompositionIssue(code=CompositionIssueCode.INVALID_REQUEST))
    if not isinstance(request.purpose, str) or not request.purpose.strip():
        issues.append(CompositionIssue(code=CompositionIssueCode.INVALID_REQUEST))
    if request.requested_output_classification is not None and not isinstance(
        request.requested_output_classification, Mapping
    ):
        issues.append(CompositionIssue(code=CompositionIssueCode.INVALID_REQUEST))

    for item in ordered:
        if not isinstance(item.source_artifact_ref, str) or not item.source_artifact_ref:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.SOURCE_ARTIFACT_UNRESOLVED,
                    input_id=item.input_id,
                )
            )
            continue

        binding = item.source_authority_binding
        if not isinstance(binding, SourceAuthorityBinding):
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.SOURCE_AUTHORITY_MISMATCH,
                    input_id=item.input_id,
                )
            )
            continue

        if item.source_artifact_ref not in binding.artifact_refs:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.SOURCE_ARTIFACT_UNRESOLVED,
                    input_id=item.input_id,
                )
            )

        if (
            item.tenant_id != binding.tenant_id
            or item.engagement_id != binding.engagement_id
            or item.classification != binding.classification
        ):
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.SOURCE_AUTHORITY_MISMATCH,
                    input_id=item.input_id,
                )
            )

        if item.provenance_binding != binding.provenance:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.PROVENANCE_MISMATCH,
                    input_id=item.input_id,
                )
            )

        if not isinstance(item.authority_disposition, AuthorityDisposition):
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.INVALID_INPUT,
                    input_id=item.input_id,
                )
            )
            continue

        if item.content_kind is CompositionContentKind.PROTECTED_FACT:
            fact = item.protected_fact
            if (
                not isinstance(fact, ProtectedDeliveryFact)
                or item.presentation_derivation is not None
            ):
                issues.append(
                    CompositionIssue(
                        code=CompositionIssueCode.CONTENT_REFERENCE_INVALID,
                        input_id=item.input_id,
                    )
                )
            elif (
                fact.source_binding != binding
                or fact.classification != item.classification
                or item.authority_disposition
                is AuthorityDisposition.PRESENTATION_ONLY
            ):
                issues.append(
                    CompositionIssue(
                        code=CompositionIssueCode.CONTENT_AUTHORITY_MISMATCH,
                        input_id=item.input_id,
                    )
                )
        elif item.content_kind is CompositionContentKind.PRESENTATION_DERIVATION:
            derivation = item.presentation_derivation
            if (
                not isinstance(derivation, PresentationDerivation)
                or item.protected_fact is not None
            ):
                issues.append(
                    CompositionIssue(
                        code=CompositionIssueCode.CONTENT_REFERENCE_INVALID,
                        input_id=item.input_id,
                    )
                )
            elif (
                derivation.tenant_id != item.tenant_id
                or derivation.engagement_id != item.engagement_id
                or derivation.classification != item.classification
                or item.authority_disposition is AuthorityDisposition.ELIGIBLE
            ):
                issues.append(
                    CompositionIssue(
                        code=CompositionIssueCode.CONTENT_AUTHORITY_MISMATCH,
                        input_id=item.input_id,
                    )
                )
        else:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.INVALID_INPUT,
                    input_id=item.input_id,
                )
            )

        if (
            item.claim_lock_evidence_ref is not None
            and (
                not isinstance(item.claim_lock_evidence_ref, str)
                or not item.claim_lock_evidence_ref.strip()
            )
        ):
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.INVALID_INPUT,
                    input_id=item.input_id,
                )
            )

    return tuple(issues)


def _scope_issues(
    request: CompositionRequest,
    ordered: tuple[CompositionInput, ...],
) -> tuple[CompositionIssue, ...]:
    issues: list[CompositionIssue] = []
    for item in ordered:
        if item.tenant_id != request.tenant_id:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.TENANT_MISMATCH,
                    input_id=item.input_id,
                )
            )
        if item.engagement_id != request.engagement_id:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.ENGAGEMENT_MISMATCH,
                    input_id=item.input_id,
                )
            )
    return tuple(issues)


def _common_classification(
    ordered: tuple[CompositionInput, ...],
) -> Mapping[str, JsonValue] | None:
    if not ordered:
        return None
    first = ordered[0].classification
    if all(item.classification == first for item in ordered[1:]):
        return first
    return None


def compose(request: CompositionRequest) -> CompositionDecision:
    if not isinstance(request, CompositionRequest):
        issues = (CompositionIssue(code=CompositionIssueCode.INVALID_REQUEST),)
        return CompositionDecision(
            disposition=AuthorityDisposition.ERROR,
            composition=None,
            issues=issues,
            evidence=CompositionEvidence(
                ordered_input_ids=(),
                input_evidence=(),
                issues=issues,
            ),
        )

    if not isinstance(request.inputs, tuple) or any(
        not isinstance(item, CompositionInput) for item in request.inputs
    ):
        issues = (CompositionIssue(code=CompositionIssueCode.INVALID_REQUEST),)
        return CompositionDecision(
            disposition=AuthorityDisposition.ERROR,
            composition=None,
            issues=issues,
            evidence=CompositionEvidence(
                ordered_input_ids=(),
                input_evidence=(),
                issues=issues,
            ),
        )

    if not request.inputs:
        issues = (CompositionIssue(code=CompositionIssueCode.EMPTY_INPUT_SET),)
        return _decision(
            AuthorityDisposition.ERROR,
            inputs=(),
            issues=issues,
        )

    ordered, ordering_issues = order_inputs(request.inputs)
    if ordering_issues:
        return _decision(
            AuthorityDisposition.ERROR,
            inputs=request.inputs,
            issues=ordering_issues,
        )

    structural = _structural_issues(request, ordered)
    if structural:
        return _decision(
            AuthorityDisposition.ERROR,
            inputs=ordered,
            issues=structural,
        )

    incoming_errors = tuple(
        CompositionIssue(
            code=CompositionIssueCode.INCOMING_ERROR,
            input_id=item.input_id,
        )
        for item in ordered
        if item.authority_disposition is AuthorityDisposition.ERROR
    )
    if incoming_errors:
        return _decision(
            AuthorityDisposition.ERROR,
            inputs=ordered,
            issues=incoming_errors,
        )

    incoming_blocks = tuple(
        CompositionIssue(
            code=CompositionIssueCode.INCOMING_BLOCK,
            input_id=item.input_id,
        )
        for item in ordered
        if item.authority_disposition is AuthorityDisposition.BLOCK
    )
    if incoming_blocks:
        return _decision(
            AuthorityDisposition.BLOCK,
            inputs=ordered,
            issues=incoming_blocks,
        )

    scope_issues = _scope_issues(request, ordered)
    if scope_issues:
        return _decision(
            AuthorityDisposition.BLOCK,
            inputs=ordered,
            issues=scope_issues,
        )

    authoritative, classification_issues = authoritative_classification(ordered)
    if classification_issues:
        return _decision(
            AuthorityDisposition.BLOCK,
            inputs=ordered,
            issues=classification_issues,
        )

    inherited = authoritative if authoritative is not None else _common_classification(ordered)
    if (
        request.requested_output_classification is not None
        and (
            inherited is None
            or request.requested_output_classification != inherited
        )
    ):
        issues = (
            CompositionIssue(
                code=CompositionIssueCode.CLASSIFICATION_CHANGE_UNAUTHORIZED
            ),
        )
        return _decision(
            AuthorityDisposition.BLOCK,
            inputs=ordered,
            issues=issues,
        )

    conflict_issues = detect_protected_fact_conflicts(ordered)
    if conflict_issues:
        return _decision(
            AuthorityDisposition.BLOCK,
            inputs=ordered,
            issues=conflict_issues,
        )

    entries = tuple(
        GovernedCompositionEntry(
            input_id=item.input_id,
            position=item.position,
            content_kind=item.content_kind,
            source_artifact_ref=item.source_artifact_ref,
            source_authority_binding=item.source_authority_binding,
            provenance_binding=item.provenance_binding,
            classification=item.classification,
            protected_fact=item.protected_fact,
            presentation_derivation=item.presentation_derivation,
            authority_disposition=item.authority_disposition,
            claim_lock_evidence_ref=item.claim_lock_evidence_ref,
        )
        for item in ordered
    )

    protected_refs = tuple(
        entry.protected_fact.fact_id
        for entry in entries
        if entry.protected_fact is not None
    )
    presentation_refs = tuple(
        entry.presentation_derivation.derivation_id
        for entry in entries
        if entry.presentation_derivation is not None
    )

    if protected_refs and presentation_refs:
        kind = CompositionKind.MIXED
    elif protected_refs:
        kind = CompositionKind.AUTHORITATIVE
    else:
        kind = CompositionKind.PRESENTATION

    disposition = (
        AuthorityDisposition.ELIGIBLE
        if protected_refs
        else AuthorityDisposition.PRESENTATION_ONLY
    )
    evidence = _evidence(ordered, ())
    aggregate = _common_classification(ordered)

    composition = GovernedComposition(
        composition_id=composition_identity(
            tenant_id=request.tenant_id,
            engagement_id=request.engagement_id,
            purpose=request.purpose,
            entries=entries,
            aggregate_classification=aggregate,
        ),
        tenant_id=request.tenant_id,
        engagement_id=request.engagement_id,
        entries=entries,
        aggregate_classification=aggregate,
        provenance_ledger=tuple(entry.provenance_binding for entry in entries),
        source_authority_ledger=tuple(
            entry.source_authority_binding for entry in entries
        ),
        protected_fact_refs=protected_refs,
        presentation_derivation_refs=presentation_refs,
        kind=kind,
        disposition=disposition,
        evidence=evidence,
    )
    return CompositionDecision(
        disposition=disposition,
        composition=composition,
        issues=(),
        evidence=evidence,
    )
