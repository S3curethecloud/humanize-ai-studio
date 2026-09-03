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

from app.v2.domain.provider_routing import (
    FallbackPolicy,
    RoutingPolicy,
)


ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_POLICY_VERSION: Literal[
    "enterprise-workspace-provider-routing-policy-v1"
] = "enterprise-workspace-provider-routing-policy-v1"


class EnterpriseProviderRoutingPolicyStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class EnterpriseWorkspaceProviderRoutingPolicy(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    policy_version: Literal[
        "enterprise-workspace-provider-routing-policy-v1"
    ] = ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_POLICY_VERSION

    policy_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    status: EnterpriseProviderRoutingPolicyStatus

    ordered_target_ids: tuple[str, ...] = Field(
        min_length=1,
    )
    fallback_policy: FallbackPolicy = Field(
        default_factory=FallbackPolicy,
    )

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
                "enterprise provider routing policy "
                "identifiers must be non-empty"
            )

        return normalized

    @model_validator(mode="after")
    def require_timestamp_integrity(
        self,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        for field_name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            if (
                value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(
                    "enterprise provider routing policy "
                    f"{field_name} must be timezone-aware"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "enterprise provider routing policy updated_at "
                "must not be before created_at"
            )

        return self

    @model_validator(mode="after")
    def require_execution_policy_integrity(
        self,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        self.to_execution_policy()
        return self

    def to_execution_policy(
        self,
    ) -> RoutingPolicy:
        return RoutingPolicy(
            policy_id=self.policy_id,
            ordered_target_ids=self.ordered_target_ids,
            fallback_policy=self.fallback_policy,
        )
