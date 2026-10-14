"""Deterministic Humanize V3.4 authority-preservation service."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from app.v2.domain.claim_lock import ClaimLock
from app.v3.ndeb.contracts import JsonValue, NdebValidationResult

from .claim_protection import evaluate_claim_protection
from .contracts import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssue,
    AuthorityIssueCode,
    AuthorityResult,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from .provenance import bind_source_authority


def _jsonable(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _jsonable(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(child) for child in value]
    return value


def _freeze_mapping(
    value: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    frozen: dict[str, JsonValue] = {}
    for key, child in value.items():
        if isinstance(child, Mapping):
            frozen[key] = _freeze_mapping(child)
        elif isinstance(child, tuple):
            frozen[key] = tuple(
                _freeze_mapping(item)
                if isinstance(item, Mapping)
                else cast(JsonValue, item)
                for item in child
            )
        else:
            frozen[key] = child
    return MappingProxyType(frozen)


def _stable_digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fact_id(binding: SourceAuthorityBinding) -> str:
    digest = _stable_digest(
        {
            "bundle_id": binding.bundle_id,
            "evidence_family": binding.evidence_family,
            "evidence_id": binding.evidence_id,
            "record_type": binding.record_type,
            "record_id": binding.record_id,
            "record_version": binding.record_version,
        }
    )
    return f"pdf:sha256:{digest}"


def _derivation_id(
    *,
    source_fact_ids: tuple[str, ...],
    tenant_id: str,
    engagement_id: str | None,
    classification: Mapping[str, JsonValue],
    text: str,
) -> str:
    digest = _stable_digest(
        {
            "source_fact_ids": list(source_fact_ids),
            "tenant_id": tenant_id,
            "engagement_id": engagement_id,
            "classification": _jsonable(classification),
            "text": text,
        }
    )
    return f"presentation:sha256:{digest}"


def bind_protected_fact(
    *,
    validated_ndeb_result: NdebValidationResult,
    authority_context: AuthorityContext,
    evidence_family: str,
    evidence_id: str,
) -> AuthorityResult[ProtectedDeliveryFact]:
    binding_result = bind_source_authority(
        validated_ndeb_result=validated_ndeb_result,
        authority_context=authority_context,
        evidence_family=evidence_family,
        evidence_id=evidence_id,
    )
    if binding_result.disposition is not AuthorityDisposition.ELIGIBLE:
        return AuthorityResult(
            disposition=binding_result.disposition,
            value=None,
            issues=binding_result.issues,
        )

    binding = binding_result.value
    if binding is None:
        return AuthorityResult(
            disposition=AuthorityDisposition.ERROR,
            value=None,
            issues=(
                AuthorityIssue(
                    code=AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
                    identifier=evidence_id,
                ),
            ),
        )

    fact = ProtectedDeliveryFact(
        fact_id=_fact_id(binding),
        source_binding=binding,
        material=binding.material,
        classification=binding.classification,
        provenance_refs=binding.provenance_refs,
    )
    return AuthorityResult(
        disposition=AuthorityDisposition.ELIGIBLE,
        value=fact,
    )


def validate_protected_fact(
    *,
    validated_ndeb_result: NdebValidationResult,
    authority_context: AuthorityContext,
    protected_fact: ProtectedDeliveryFact,
) -> AuthorityResult[ProtectedDeliveryFact]:
    rebound = bind_source_authority(
        validated_ndeb_result=validated_ndeb_result,
        authority_context=authority_context,
        evidence_family=protected_fact.source_binding.evidence_family,
        evidence_id=protected_fact.source_binding.evidence_id,
    )
    if rebound.disposition is not AuthorityDisposition.ELIGIBLE:
        return AuthorityResult(
            disposition=rebound.disposition,
            value=None,
            issues=rebound.issues,
        )

    binding = rebound.value
    if binding is None:
        return AuthorityResult(
            disposition=AuthorityDisposition.ERROR,
            value=None,
            issues=(
                AuthorityIssue(
                    code=AuthorityIssueCode.SOURCE_RECORD_UNRESOLVED,
                    identifier=protected_fact.source_binding.evidence_id,
                ),
            ),
        )

    exact = (
        protected_fact.source_binding == binding
        and protected_fact.fact_id == _fact_id(binding)
        and protected_fact.material == binding.material
        and protected_fact.classification == binding.classification
        and protected_fact.provenance_refs == binding.provenance_refs
    )
    if not exact:
        return AuthorityResult(
            disposition=AuthorityDisposition.BLOCK,
            value=None,
            issues=(
                AuthorityIssue(
                    code=AuthorityIssueCode.PROTECTED_FACT_SOURCE_MISMATCH,
                    identifier=protected_fact.fact_id,
                ),
            ),
        )

    return AuthorityResult(
        disposition=AuthorityDisposition.ELIGIBLE,
        value=protected_fact,
    )


def derive_presentation(
    *,
    validated_ndeb_result: NdebValidationResult,
    authority_context: AuthorityContext,
    source_protected_facts: tuple[ProtectedDeliveryFact, ...],
    presentation_text: str,
    effective_claim_lock: ClaimLock | None = None,
    classification_override: Mapping[str, JsonValue] | None = None,
) -> AuthorityResult[PresentationDerivation]:
    if not source_protected_facts:
        return AuthorityResult(
            disposition=AuthorityDisposition.ERROR,
            value=None,
            issues=(
                AuthorityIssue(
                    code=AuthorityIssueCode.UNSUPPORTED_AUTHORITY_TRANSFORMATION,
                ),
            ),
        )

    validated_facts: list[ProtectedDeliveryFact] = []
    for fact in source_protected_facts:
        validation = validate_protected_fact(
            validated_ndeb_result=validated_ndeb_result,
            authority_context=authority_context,
            protected_fact=fact,
        )
        if validation.disposition is not AuthorityDisposition.ELIGIBLE:
            return AuthorityResult(
                disposition=validation.disposition,
                value=None,
                issues=validation.issues,
            )
        if validation.value is None:
            return AuthorityResult(
                disposition=AuthorityDisposition.ERROR,
                value=None,
                issues=(
                    AuthorityIssue(
                        code=AuthorityIssueCode.PROTECTED_FACT_SOURCE_MISMATCH,
                        identifier=fact.fact_id,
                    ),
                ),
            )
        validated_facts.append(validation.value)

    source_classification = validated_facts[0].classification
    if any(
        fact.classification != source_classification
        for fact in validated_facts[1:]
    ):
        return AuthorityResult(
            disposition=AuthorityDisposition.BLOCK,
            value=None,
            issues=(
                AuthorityIssue(
                    code=AuthorityIssueCode.CLASSIFICATION_CHANGE_UNAUTHORIZED,
                ),
            ),
        )

    if classification_override is None:
        classification = source_classification
    else:
        frozen_override = _freeze_mapping(classification_override)
        if frozen_override != source_classification:
            return AuthorityResult(
                disposition=AuthorityDisposition.BLOCK,
                value=None,
                issues=(
                    AuthorityIssue(
                        code=AuthorityIssueCode.CLASSIFICATION_CHANGE_UNAUTHORIZED,
                    ),
                ),
            )
        classification = source_classification

    assessment = evaluate_claim_protection(
        claim_lock=effective_claim_lock,
        presentation_text=presentation_text,
    )
    if assessment.blocks:
        return AuthorityResult(
            disposition=AuthorityDisposition.BLOCK,
            value=None,
            issues=assessment.issues,
        )

    source_fact_ids = tuple(fact.fact_id for fact in validated_facts)
    derivation = PresentationDerivation(
        derivation_id=_derivation_id(
            source_fact_ids=source_fact_ids,
            tenant_id=authority_context.tenant_id,
            engagement_id=authority_context.engagement_id,
            classification=classification,
            text=presentation_text,
        ),
        source_fact_ids=source_fact_ids,
        tenant_id=authority_context.tenant_id,
        engagement_id=authority_context.engagement_id,
        classification=classification,
        text=presentation_text,
        claim_lock_validation=assessment.validation,
    )
    return AuthorityResult(
        disposition=AuthorityDisposition.PRESENTATION_ONLY,
        value=derivation,
        issues=assessment.issues,
    )
