from __future__ import annotations

import pytest

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
    ProtectedValue,
    ProtectedValueKind,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockCheckStatus,
    ClaimLockValidationDecision,
    ClaimLockValidator,
)


def _provenance() -> ClaimLockProvenance:
    return ClaimLockProvenance(
        origin=ClaimLockOrigin.REQUEST,
        source_reference="adversarial-test",
    )


@pytest.mark.parametrize(
    (
        "expected",
        "rewritten",
        "case_sensitive",
    ),
    (
        (
            "SecureTheCloud",
            "SecureTheCl0ud is approved.",
            True,
        ),
        (
            "SecureTheCloud",
            "securethecloud is approved.",
            True,
        ),
        (
            "Human Review",
            "Human-Review is required.",
            False,
        ),
    ),
)
def test_protected_term_mutation_is_detected(
    expected: str,
    rewritten: str,
    case_sensitive: bool,
) -> None:
    lock = ClaimLock(
        lock_id="lock-term-adversarial",
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        terms=(
            ProtectedTerm(
                term_id="term-1",
                text=expected,
                case_sensitive=case_sensitive,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=rewritten,
    )

    assert result.decision is ClaimLockValidationDecision.VIOLATION
    assert result.checks[0].status is ClaimLockCheckStatus.MISSING


@pytest.mark.parametrize(
    (
        "kind",
        "expected",
        "rewritten",
    ),
    (
        (
            ProtectedValueKind.NUMBER,
            "$42,500.75",
            "Revenue was $42,500.76.",
        ),
        (
            ProtectedValueKind.PERCENTAGE,
            "42%",
            "Completion reached 43%.",
        ),
        (
            ProtectedValueKind.DATE,
            "2026-08-11",
            "The release date is 2026-08-12.",
        ),
        (
            ProtectedValueKind.URL,
            "https://securethecloud.dev/policy",
            "See https://securethecloud.dev/policies.",
        ),
        (
            ProtectedValueKind.IDENTIFIER,
            "ABC123456",
            "The identifier is ABC123457.",
        ),
        (
            ProtectedValueKind.CODE,
            "POL-AI-001",
            "The active policy is POL-AI-002.",
        ),
    ),
)
def test_protected_value_drift_is_detected(
    kind: ProtectedValueKind,
    expected: str,
    rewritten: str,
) -> None:
    lock = ClaimLock(
        lock_id="lock-value-adversarial",
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        values=(
            ProtectedValue(
                value_id="value-1",
                value=expected,
                kind=kind,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=rewritten,
    )

    assert result.decision is ClaimLockValidationDecision.VIOLATION
    assert result.violating_item_ids == ("value-1",)


@pytest.mark.parametrize(
    (
        "kind",
        "expected",
        "rewritten",
    ),
    (
        (
            ProtectedValueKind.NUMBER,
            "42",
            "The approved value remains 42.",
        ),
        (
            ProtectedValueKind.PERCENTAGE,
            "42%",
            "Completion remains exactly 42%.",
        ),
        (
            ProtectedValueKind.DATE,
            "2026-08-11",
            "The release remains 2026-08-11.",
        ),
        (
            ProtectedValueKind.URL,
            "https://securethecloud.dev/policy",
            ("See https://securethecloud.dev/policy for details."),
        ),
        (
            ProtectedValueKind.IDENTIFIER,
            "ABC123456",
            "Identifier ABC123456 remains active.",
        ),
        (
            ProtectedValueKind.CODE,
            "POL-AI-001",
            "Policy POL-AI-001 remains active.",
        ),
    ),
)
def test_exact_protected_values_survive_adversarial_validation(
    kind: ProtectedValueKind,
    expected: str,
    rewritten: str,
) -> None:
    lock = ClaimLock(
        lock_id="lock-value-preserved",
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        values=(
            ProtectedValue(
                value_id="value-1",
                value=expected,
                kind=kind,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=rewritten,
    )

    assert result.decision is ClaimLockValidationDecision.PASS
    assert result.checks[0].status is ClaimLockCheckStatus.PRESERVED
