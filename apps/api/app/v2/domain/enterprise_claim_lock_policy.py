from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ProtectedTerm,
)

ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION: Literal[
    "enterprise-workspace-claim-lock-policy-v1"
] = "enterprise-workspace-claim-lock-policy-v1"


class EnterpriseClaimLockPolicyStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class EnterpriseWorkspaceClaimLockPolicy(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    policy_version: Literal[
        "enterprise-workspace-claim-lock-policy-v1"
    ] = ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION

    policy_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    status: EnterpriseClaimLockPolicyStatus
    enforcement_mode: ClaimLockEnforcementMode

    protected_terms: tuple[
        ProtectedTerm,
        ...,
    ]

    created_by_user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    created_at: datetime

    updated_by_user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    updated_at: datetime

    revision: int = Field(
        ge=1,
    )

    @field_validator(
        "policy_id",
        "workspace_id",
        "created_by_user_id",
        "updated_by_user_id",
        mode="before",
    )
    @classmethod
    def normalize_identifier(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "enterprise claim lock policy identifiers "
                "must be non-empty"
            )

        return normalized

    @model_validator(mode="after")
    def require_timestamp_integrity(
        self,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        for field_name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            if (
                value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(
                    "enterprise claim lock policy "
                    f"{field_name} must be timezone-aware"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "enterprise claim lock policy updated_at "
                "must not be before created_at"
            )

        return self

    @model_validator(mode="after")
    def require_workspace_term_provenance(
        self,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        expected_source_reference = (
            "workspace-claim-lock-policy:"
            f"{self.policy_id}:revision:{self.revision}"
        )

        for term in self.protected_terms:
            if (
                term.provenance.origin
                is not ClaimLockOrigin.WORKSPACE
            ):
                raise ValueError(
                    "enterprise claim lock policy protected "
                    "terms must have workspace provenance"
                )

            if (
                term.provenance.source_reference
                != expected_source_reference
            ):
                raise ValueError(
                    "enterprise claim lock policy protected "
                    "term provenance must reference the "
                    "current policy revision"
                )

        return self

    @model_validator(mode="after")
    def reject_duplicate_terms(
        self,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        identifiers = tuple(
            term.term_id.casefold()
            for term in self.protected_terms
        )

        if len(set(identifiers)) != len(identifiers):
            raise ValueError(
                "enterprise claim lock policy contains "
                "duplicate protected term identifiers"
            )

        semantic_keys = tuple(
            term.semantic_key()
            for term in self.protected_terms
        )

        if len(set(semantic_keys)) != len(semantic_keys):
            raise ValueError(
                "enterprise claim lock policy contains "
                "duplicate protected terms"
            )

        return self
