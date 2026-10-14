from __future__ import annotations

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedClaim,
    ProtectedTerm,
    ProtectedValue,
    ProtectedValueKind,
)
from app.v2.services.claim_lock_validator import ClaimLockCheckStatus
from app.v3.authority import AuthorityIssueCode, evaluate_claim_protection


def _provenance() -> ClaimLockProvenance:
    return ClaimLockProvenance(
        origin=ClaimLockOrigin.REQUEST,
        source_reference="v3.4-test",
    )


def test_strict_missing_protected_term_blocks() -> None:
    lock = ClaimLock(
        lock_id="strict-term",
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        terms=(
            ProtectedTerm(
                term_id="term-1",
                text="Approved Term",
                provenance=_provenance(),
            ),
        ),
    )

    assessment = evaluate_claim_protection(
        claim_lock=lock,
        presentation_text="Different wording.",
    )

    assert assessment.blocks is True
    assert assessment.issues[0].code is AuthorityIssueCode.CLAIM_LOCK_STRICT_VIOLATION


def test_strict_missing_protected_value_blocks() -> None:
    lock = ClaimLock(
        lock_id="strict-value",
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        values=(
            ProtectedValue(
                value_id="value-1",
                value="42%",
                kind=ProtectedValueKind.PERCENTAGE,
                provenance=_provenance(),
            ),
        ),
    )

    assessment = evaluate_claim_protection(
        claim_lock=lock,
        presentation_text="The value changed.",
    )

    assert assessment.blocks is True
    assert assessment.issues[0].identifier == "value-1"


def test_preserved_deterministic_content_does_not_violate() -> None:
    lock = ClaimLock(
        lock_id="preserved",
        terms=(
            ProtectedTerm(
                term_id="term-1",
                text="Approved Term",
                provenance=_provenance(),
            ),
        ),
    )

    assessment = evaluate_claim_protection(
        claim_lock=lock,
        presentation_text="Approved Term remains unchanged.",
    )

    assert assessment.blocks is False
    assert assessment.issues == ()


def test_audit_only_violation_is_evidence_not_block() -> None:
    lock = ClaimLock(
        lock_id="audit",
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
        terms=(
            ProtectedTerm(
                term_id="term-1",
                text="Approved Term",
                provenance=_provenance(),
            ),
        ),
    )

    assessment = evaluate_claim_protection(
        claim_lock=lock,
        presentation_text="Different wording.",
    )

    assert assessment.blocks is False
    assert assessment.issues[0].code is AuthorityIssueCode.CLAIM_LOCK_AUDIT_VIOLATION


def test_semantic_claim_remains_not_evaluated() -> None:
    lock = ClaimLock(
        lock_id="semantic",
        claims=(
            ProtectedClaim(
                claim_id="claim-1",
                text="The architecture decision is approved.",
                provenance=_provenance(),
            ),
        ),
    )

    assessment = evaluate_claim_protection(
        claim_lock=lock,
        presentation_text="The architecture decision is changed.",
    )

    assert assessment.blocks is False
    assert assessment.validation.checks[0].status is ClaimLockCheckStatus.NOT_EVALUATED
    assert (
        assessment.issues[0].code
        is AuthorityIssueCode.CLAIM_LOCK_SEMANTIC_NOT_EVALUATED
    )
