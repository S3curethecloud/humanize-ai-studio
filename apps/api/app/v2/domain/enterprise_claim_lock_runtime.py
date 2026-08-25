from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
)

ENTERPRISE_CLAIM_LOCK_RUNTIME_VERSION: Literal[
    "enterprise-claim-lock-runtime-v1"
] = "enterprise-claim-lock-runtime-v1"

ENTERPRISE_CLAIM_LOCK_WORKSPACE_POLICY_EXECUTION_VERSION: Literal[
    "enterprise-claim-lock-workspace-policy-execution-v1"
] = "enterprise-claim-lock-workspace-policy-execution-v1"


class EnterpriseClaimLockWorkspacePolicyExecutionEvidence(
    BaseModel,
):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    evidence_version: Literal[
        "enterprise-claim-lock-workspace-policy-execution-v1"
    ] = ENTERPRISE_CLAIM_LOCK_WORKSPACE_POLICY_EXECUTION_VERSION

    policy_version: Literal[
        "enterprise-workspace-claim-lock-policy-v1"
    ] = ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION

    policy_id: str = Field(
        min_length=1,
        max_length=200,
    )
    policy_revision: int = Field(
        ge=1,
    )
    enforcement_mode: ClaimLockEnforcementMode
    applicable_term_ids: tuple[
        str,
        ...,
    ] = ()

    @field_validator(
        "policy_id",
        mode="before",
    )
    @classmethod
    def normalize_policy_id(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "enterprise claim lock workspace policy "
                "execution policy_id must be non-empty"
            )

        return normalized

    @field_validator(
        "applicable_term_ids",
    )
    @classmethod
    def require_applicable_term_id_integrity(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for term_id in value:
            candidate = term_id.strip()

            if not candidate:
                raise ValueError(
                    "enterprise claim lock workspace policy "
                    "applicable term identifiers must be non-empty"
                )

            if len(candidate) > 200:
                raise ValueError(
                    "enterprise claim lock workspace policy "
                    "applicable term identifiers must not exceed "
                    "200 characters"
                )

            normalized.append(candidate)

        casefolded = tuple(
            term_id.casefold()
            for term_id in normalized
        )

        if len(set(casefolded)) != len(casefolded):
            raise ValueError(
                "enterprise claim lock workspace policy "
                "applicable term identifiers must be unique"
            )

        return tuple(normalized)


class EnterpriseClaimLockRuntimeContext(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    runtime_version: Literal[
        "enterprise-claim-lock-runtime-v1"
    ] = ENTERPRISE_CLAIM_LOCK_RUNTIME_VERSION

    request_preparation: ClaimLockPreparationResult
    effective_claim_lock: ClaimLock | None = None
    workspace_policy_evidence: (
        EnterpriseClaimLockWorkspacePolicyExecutionEvidence
        | None
    ) = None
    request_customization_requested: bool
    effective_enforcement_mode: ClaimLockEnforcementMode

    @model_validator(mode="after")
    def require_runtime_integrity(
        self,
    ) -> EnterpriseClaimLockRuntimeContext:
        if (
            self.effective_claim_lock is not None
            and self.effective_claim_lock.enforcement_mode
            is not self.effective_enforcement_mode
        ):
            raise ValueError(
                "enterprise claim lock effective lock mode "
                "must match runtime effective enforcement mode"
            )

        if (
            self.request_preparation.claim_lock is not None
            and self.effective_claim_lock is None
        ):
            raise ValueError(
                "enterprise claim lock runtime cannot discard "
                "prepared protected items"
            )

        return self
