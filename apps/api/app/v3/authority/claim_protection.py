"""Adapter from V3.4 presentation authority to the existing Claim Lock validator."""

from __future__ import annotations

from dataclasses import dataclass

from app.v2.domain.claim_lock import ClaimLock, ClaimLockEnforcementMode
from app.v2.services.claim_lock_validator import (
    ClaimLockCheckStatus,
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
    ClaimLockValidator,
)

from .contracts import AuthorityIssue, AuthorityIssueCode


@dataclass(frozen=True)
class ClaimProtectionAssessment:
    validation: ClaimLockValidationResult
    issues: tuple[AuthorityIssue, ...]
    blocks: bool


def evaluate_claim_protection(
    *,
    claim_lock: ClaimLock | None,
    presentation_text: str,
) -> ClaimProtectionAssessment:
    validation = ClaimLockValidator().validate(
        claim_lock=claim_lock,
        rewritten_text=presentation_text,
    )

    issues: list[AuthorityIssue] = []

    for check in validation.checks:
        if (
            check.item_type == "claim"
            and check.status is ClaimLockCheckStatus.NOT_EVALUATED
        ):
            issues.append(
                AuthorityIssue(
                    code=AuthorityIssueCode.CLAIM_LOCK_SEMANTIC_NOT_EVALUATED,
                    identifier=check.item_id,
                )
            )

    blocks = False
    if validation.decision is ClaimLockValidationDecision.VIOLATION:
        if validation.enforcement_mode is ClaimLockEnforcementMode.STRICT:
            blocks = True
            for item_id in validation.violating_item_ids:
                issues.append(
                    AuthorityIssue(
                        code=AuthorityIssueCode.CLAIM_LOCK_STRICT_VIOLATION,
                        identifier=item_id,
                    )
                )
        else:
            for item_id in validation.violating_item_ids:
                issues.append(
                    AuthorityIssue(
                        code=AuthorityIssueCode.CLAIM_LOCK_AUDIT_VIOLATION,
                        identifier=item_id,
                    )
                )

    return ClaimProtectionAssessment(
        validation=validation,
        issues=tuple(issues),
        blocks=blocks,
    )
