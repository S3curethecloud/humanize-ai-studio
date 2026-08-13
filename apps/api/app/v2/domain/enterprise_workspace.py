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

ENTERPRISE_WORKSPACE_VERSION: Literal["enterprise-workspace-v1"] = "enterprise-workspace-v1"

ENTERPRISE_MEMBERSHIP_VERSION: Literal["enterprise-membership-v1"] = "enterprise-membership-v1"


class EnterpriseWorkspaceStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class EnterpriseMembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class EnterpriseWorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class EnterpriseOrganization(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    organization_id: str = Field(
        min_length=1,
        max_length=200,
    )

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    created_by_user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def require_integrity(
        self,
    ) -> EnterpriseOrganization:
        _require_timezone_aware(
            self.created_at,
            field_name="organization created_at",
        )

        return self


class EnterpriseWorkspace(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    workspace_version: Literal["enterprise-workspace-v1"] = ENTERPRISE_WORKSPACE_VERSION

    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    organization_id: str = Field(
        min_length=1,
        max_length=200,
    )

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    created_by_user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    status: EnterpriseWorkspaceStatus = EnterpriseWorkspaceStatus.ACTIVE

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def require_integrity(
        self,
    ) -> EnterpriseWorkspace:
        _require_timezone_aware(
            self.created_at,
            field_name="workspace created_at",
        )

        _require_timezone_aware(
            self.updated_at,
            field_name="workspace updated_at",
        )

        if self.updated_at < self.created_at:
            raise ValueError("workspace updated_at cannot precede created_at")

        return self


class EnterpriseWorkspaceMembership(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    membership_version: Literal["enterprise-membership-v1"] = ENTERPRISE_MEMBERSHIP_VERSION

    membership_id: str = Field(
        min_length=1,
        max_length=200,
    )

    organization_id: str = Field(
        min_length=1,
        max_length=200,
    )

    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    role: EnterpriseWorkspaceRole

    status: EnterpriseMembershipStatus = EnterpriseMembershipStatus.ACTIVE

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def require_integrity(
        self,
    ) -> EnterpriseWorkspaceMembership:
        _require_timezone_aware(
            self.created_at,
            field_name="membership created_at",
        )

        _require_timezone_aware(
            self.updated_at,
            field_name="membership updated_at",
        )

        if self.updated_at < self.created_at:
            raise ValueError("membership updated_at cannot precede created_at")

        return self


def _require_timezone_aware(
    value: datetime,
    *,
    field_name: str,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
