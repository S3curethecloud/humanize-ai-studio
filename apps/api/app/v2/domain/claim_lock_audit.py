from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
)


class ClaimLockValidationAuditCheck(BaseModel):
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
    status: Literal[
        "preserved",
        "missing",
        "not_evaluated",
    ]
    reason: str = Field(
        min_length=1,
        max_length=1000,
    )


class ClaimLockValidationAuditSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    validator_version: Literal["claim-lock-validator-v1"]
    lock_id: str = Field(
        min_length=1,
        max_length=200,
    )
    enforcement_mode: ClaimLockEnforcementMode
    decision: Literal[
        "pass",
        "violation",
    ]
    checks: tuple[
        ClaimLockValidationAuditCheck,
        ...,
    ] = ()

    @model_validator(mode="after")
    def require_decision_matches_checks(
        self,
    ) -> ClaimLockValidationAuditSnapshot:
        has_missing = any(check.status == "missing" for check in self.checks)

        if self.decision == "violation" and not has_missing:
            raise ValueError("violation decision requires at least one missing item")

        if self.decision == "pass" and has_missing:
            raise ValueError("pass decision must not contain missing items")

        return self


class ClaimLockHistoryAuditEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_lock_snapshot: ClaimLock
    claim_lock_validation: ClaimLockValidationAuditSnapshot
    claim_lock_enforcement_mode: ClaimLockEnforcementMode

    @model_validator(mode="after")
    def require_coherent_claim_lock_audit(
        self,
    ) -> ClaimLockHistoryAuditEvidence:
        if self.claim_lock_snapshot.lock_id != self.claim_lock_validation.lock_id:
            raise ValueError("claim lock validation lock_id must match snapshot")

        if self.claim_lock_snapshot.enforcement_mode is not self.claim_lock_enforcement_mode:
            raise ValueError("claim lock snapshot enforcement mode mismatch")

        if self.claim_lock_validation.enforcement_mode is not self.claim_lock_enforcement_mode:
            raise ValueError("claim lock validation enforcement mode mismatch")

        return self
