from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

ENTERPRISE_ADMIN_AUDIT_VERSION: Literal[
    "enterprise-admin-audit-v1"
] = "enterprise-admin-audit-v1"


class EnterpriseAdminAuditAction(StrEnum):
    QUOTA_LIMIT_CREATE = "quota_limit_create"
    QUOTA_LIMIT_GET = "quota_limit_get"
    QUOTA_LIMIT_LIST = "quota_limit_list"

    CLAIM_LOCK_POLICY_CREATE = "claim_lock_policy_create"
    CLAIM_LOCK_POLICY_UPDATE = "claim_lock_policy_update"
    CLAIM_LOCK_POLICY_ENABLE = "claim_lock_policy_enable"
    CLAIM_LOCK_POLICY_DISABLE = "claim_lock_policy_disable"
    CLAIM_LOCK_POLICY_ARCHIVE = "claim_lock_policy_archive"


class EnterpriseAdminAuditOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"


class EnterpriseAdminAuditEvent(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    audit_version: Literal[
        "enterprise-admin-audit-v1"
    ] = ENTERPRISE_ADMIN_AUDIT_VERSION

    audit_event_id: str = Field(
        min_length=1,
        max_length=200,
    )

    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    actor_user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    action: EnterpriseAdminAuditAction
    outcome: EnterpriseAdminAuditOutcome

    target_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    target_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    failure_reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    @model_validator(mode="after")
    def require_audit_integrity(
        self,
    ) -> EnterpriseAdminAuditEvent:
        if (
            self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError(
                "enterprise admin audit timestamp "
                "must be timezone-aware"
            )

        if (
            self.target_id is not None
            and self.target_type is None
        ):
            raise ValueError(
                "enterprise admin audit target_id "
                "requires target_type"
            )

        if (
            self.outcome
            is EnterpriseAdminAuditOutcome.SUCCEEDED
        ):
            if self.failure_reason is not None:
                raise ValueError(
                    "successful enterprise admin audit "
                    "cannot contain failure_reason"
                )

            return self

        if self.failure_reason is None:
            raise ValueError(
                "denied or failed enterprise admin audit "
                "requires failure_reason"
            )

        return self
