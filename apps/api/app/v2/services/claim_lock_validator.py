from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
)

_VALIDATOR_VERSION: Literal["claim-lock-validator-v1"] = "claim-lock-validator-v1"


class ClaimLockValidationDecision(StrEnum):
    PASS = "pass"
    VIOLATION = "violation"


class ClaimLockCheckStatus(StrEnum):
    PRESERVED = "preserved"
    MISSING = "missing"
    NOT_EVALUATED = "not_evaluated"


class ClaimLockValidationCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str = Field(
        min_length=1,
        max_length=200,
    )
    item_type: Literal[
        "claim",
        "term",
        "value",
    ]
    expected_text: str = Field(
        min_length=1,
        max_length=10_000,
    )
    status: ClaimLockCheckStatus
    reason: str = Field(
        min_length=1,
        max_length=1000,
    )


class ClaimLockValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    validator_version: Literal["claim-lock-validator-v1"] = _VALIDATOR_VERSION

    lock_id: str | None = Field(
        default=None,
        max_length=200,
    )
    enforcement_mode: ClaimLockEnforcementMode | None = None

    decision: ClaimLockValidationDecision

    checks: tuple[
        ClaimLockValidationCheck,
        ...,
    ] = ()

    @property
    def violating_item_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            check.item_id for check in self.checks if (check.status is ClaimLockCheckStatus.MISSING)
        )

    @property
    def unevaluated_claim_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            check.item_id
            for check in self.checks
            if (check.item_type == "claim" and check.status is ClaimLockCheckStatus.NOT_EVALUATED)
        )


class ClaimLockViolationError(ValueError):
    def __init__(
        self,
        validation: ClaimLockValidationResult,
    ) -> None:
        self.validation = validation

        violating_ids = ", ".join(validation.violating_item_ids)

        super().__init__(
            "claim lock strict enforcement failed" + (f": {violating_ids}" if violating_ids else "")
        )


class ClaimLockValidator:
    def validate(
        self,
        *,
        claim_lock: ClaimLock | None,
        rewritten_text: str,
    ) -> ClaimLockValidationResult:
        if claim_lock is None:
            return ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )

        checks: list[ClaimLockValidationCheck] = []

        for claim in claim_lock.claims:
            checks.append(
                ClaimLockValidationCheck(
                    item_id=claim.claim_id,
                    item_type="claim",
                    expected_text=claim.text,
                    status=(ClaimLockCheckStatus.NOT_EVALUATED),
                    reason=(
                        "semantic claim preservation is not "
                        "deterministically evaluated by "
                        "claim-lock-validator-v1"
                    ),
                )
            )

        for term in claim_lock.terms:
            if term.case_sensitive:
                preserved = term.text in rewritten_text
            else:
                preserved = term.text.casefold() in rewritten_text.casefold()

            checks.append(
                ClaimLockValidationCheck(
                    item_id=term.term_id,
                    item_type="term",
                    expected_text=term.text,
                    status=(
                        ClaimLockCheckStatus.PRESERVED
                        if preserved
                        else ClaimLockCheckStatus.MISSING
                    ),
                    reason=(
                        "protected term is present" if preserved else "protected term is missing"
                    ),
                )
            )

        for value in claim_lock.values:
            preserved = value.value in rewritten_text

            checks.append(
                ClaimLockValidationCheck(
                    item_id=value.value_id,
                    item_type="value",
                    expected_text=value.value,
                    status=(
                        ClaimLockCheckStatus.PRESERVED
                        if preserved
                        else ClaimLockCheckStatus.MISSING
                    ),
                    reason=(
                        "protected value is present" if preserved else "protected value is missing"
                    ),
                )
            )

        decision = (
            ClaimLockValidationDecision.VIOLATION
            if any(check.status is ClaimLockCheckStatus.MISSING for check in checks)
            else ClaimLockValidationDecision.PASS
        )

        return ClaimLockValidationResult(
            lock_id=claim_lock.lock_id,
            enforcement_mode=(claim_lock.enforcement_mode),
            decision=decision,
            checks=tuple(checks),
        )
