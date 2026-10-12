"""Deterministic provider-free NDEB validation orchestrator."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from .contracts import (
    ERROR_CODES,
    REJECT_CODES,
    SUPPORTED_SCHEMA_ID,
    SUPPORTED_SCHEMA_VERSION,
    JsonValue,
    NdebAuthorizedContext,
    NdebDisposition,
    NdebIssueCode,
    NdebValidationIssue,
    NdebValidationResult,
)
from .integrity import IntegrityValidationResult, normalize_nfc, validate_integrity
from .parser import NdebParseFailure, parse_candidate
from .schema_validation import validate_structure
from .semantic_validation import validate_semantics


def _freeze(value: Any) -> JsonValue:
    if isinstance(value, dict):
        frozen = {str(key): _freeze(child) for key, child in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("unsupported JSON value")


def _result(
    issues: list[NdebValidationIssue],
    *,
    bundle: dict[str, Any] | None = None,
    computed_digest: str | None = None,
) -> NdebValidationResult:
    ordered = tuple(sorted(set(issues), key=lambda item: (item.code.value, item.json_pointer)))
    if any(issue.code in ERROR_CODES for issue in ordered):
        disposition = NdebDisposition.ERROR
    elif any(issue.code in REJECT_CODES for issue in ordered):
        disposition = NdebDisposition.REJECTED
    else:
        disposition = NdebDisposition.VALIDATED
    validated_bundle: Mapping[str, JsonValue] | None = None
    if disposition is NdebDisposition.VALIDATED and bundle is not None:
        frozen = _freeze(bundle)
        if not isinstance(frozen, MappingProxyType):
            raise TypeError("validated root must be mapping")
        validated_bundle = frozen
    return NdebValidationResult(disposition, ordered, validated_bundle, computed_digest)


def _terminal_identity_gate(candidate: dict[str, Any]) -> NdebValidationResult | None:
    schema_id = candidate.get("schema_id")
    if not isinstance(schema_id, str) or not schema_id:
        return _result([NdebValidationIssue(NdebIssueCode.SCHEMA_IDENTITY_MISSING, "/schema_id")])
    if schema_id != SUPPORTED_SCHEMA_ID:
        return _result(
            [NdebValidationIssue(NdebIssueCode.SCHEMA_IDENTITY_UNSUPPORTED, "/schema_id")]
        )
    schema_version = candidate.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        return _result(
            [NdebValidationIssue(NdebIssueCode.SCHEMA_VERSION_MISSING, "/schema_version")]
        )
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        return _result(
            [NdebValidationIssue(NdebIssueCode.SCHEMA_VERSION_UNSUPPORTED, "/schema_version")]
        )
    return None


def _context_issues(
    candidate: dict[str, Any],
    context: NdebAuthorizedContext,
) -> tuple[NdebValidationIssue, ...]:
    issues: list[NdebValidationIssue] = []
    if not isinstance(context.tenant_id, str) or not context.tenant_id:
        issues.append(NdebValidationIssue(NdebIssueCode.TENANT_CONTEXT_UNAVAILABLE, ""))
    elif (
        isinstance(candidate.get("tenant_id"), str) and candidate["tenant_id"] != context.tenant_id
    ):
        issues.append(NdebValidationIssue(NdebIssueCode.TENANT_SCOPE_MISMATCH, "/tenant_id"))
    if not isinstance(context.engagement_id, str) or not context.engagement_id:
        issues.append(NdebValidationIssue(NdebIssueCode.ENGAGEMENT_CONTEXT_UNAVAILABLE, ""))
    elif (
        isinstance(candidate.get("engagement_id"), str)
        and candidate["engagement_id"] != context.engagement_id
    ):
        issues.append(
            NdebValidationIssue(NdebIssueCode.ENGAGEMENT_SCOPE_MISMATCH, "/engagement_id")
        )
    if context.classification is not None:
        classification = candidate.get("classification")
        if not isinstance(classification, dict):
            issues.append(
                NdebValidationIssue(NdebIssueCode.CLASSIFICATION_INVALID, "/classification")
            )
        else:
            expected = normalize_nfc(dict(context.classification))
            observed = normalize_nfc(classification)
            if expected != observed:
                issues.append(
                    NdebValidationIssue(
                        NdebIssueCode.CLASSIFICATION_CONTEXT_MISMATCH,
                        "/classification",
                    )
                )
    return tuple(issues)


def validate_ndeb_bundle(
    *,
    candidate_bytes: bytes,
    context: NdebAuthorizedContext,
) -> NdebValidationResult:
    try:
        candidate = parse_candidate(candidate_bytes)
    except NdebParseFailure as exc:
        return _result([NdebValidationIssue(exc.code, exc.json_pointer)])
    except Exception:
        return _result([NdebValidationIssue(NdebIssueCode.VALIDATOR_INTERNAL_ERROR, "")])

    terminal = _terminal_identity_gate(candidate)
    if terminal is not None:
        return terminal

    try:
        structural = validate_structure(candidate)
        issues = list(structural.issues)
        structural_error = any(issue.code in ERROR_CODES for issue in structural.issues)
        computed_digest: str | None = None
        if not structural_error:
            issues.extend(validate_semantics(candidate))
            semantic_error = any(issue.code in ERROR_CODES for issue in issues)
            if not structural.unsupported_integrity_contract and not semantic_error:
                integrity: IntegrityValidationResult = validate_integrity(candidate)
                issues.extend(integrity.issues)
                computed_digest = integrity.computed_digest_sha256
            issues.extend(_context_issues(candidate, context))
        else:
            issues.extend(_context_issues(candidate, context))
        return _result(issues, bundle=candidate, computed_digest=computed_digest)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return _result([NdebValidationIssue(NdebIssueCode.VALIDATOR_INTERNAL_ERROR, "")])
