from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

ENTERPRISE_QUOTA_CONTRACT_VERSION: Literal["enterprise-quota-v1"] = "enterprise-quota-v1"

ENTERPRISE_QUOTA_LIMIT_VERSION: Literal["enterprise-quota-limit-v1"] = "enterprise-quota-limit-v1"

ENTERPRISE_QUOTA_ACCOUNTING_VERSION: Literal["enterprise-quota-accounting-v1"] = (
    "enterprise-quota-accounting-v1"
)


class EnterpriseQuotaDimension(StrEnum):
    REWRITE_REQUESTS = "rewrite_requests"
    INPUT_CHARACTERS = "input_characters"
    OUTPUT_CHARACTERS = "output_characters"
    CANDIDATES_GENERATED = "candidates_generated"
    LONG_DOCUMENT_SECTIONS = "long_document_sections"


class EnterpriseQuotaOperation(StrEnum):
    SINGLE_REWRITE = "single_rewrite"
    MULTI_CANDIDATE_REWRITE = "multi_candidate_rewrite"
    LONG_DOCUMENT_REWRITE = "long_document_rewrite"


_OPERATION_DIMENSIONS: dict[
    EnterpriseQuotaOperation,
    frozenset[EnterpriseQuotaDimension],
] = {
    EnterpriseQuotaOperation.SINGLE_REWRITE: frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
        }
    ),
    EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE: frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
            EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        }
    ),
    EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE: frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
            EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
        }
    ),
}


class EnterpriseQuotaWindow(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    window_start: datetime
    window_end: datetime

    @model_validator(mode="after")
    def require_window_integrity(
        self,
    ) -> EnterpriseQuotaWindow:
        _require_timezone_aware(
            self.window_start,
            field_name="window_start",
        )
        _require_timezone_aware(
            self.window_end,
            field_name="window_end",
        )

        if self.window_end <= self.window_start:
            raise ValueError("enterprise quota window_end must be after window_start")

        return self

    def contains(
        self,
        value: datetime,
    ) -> bool:
        _require_timezone_aware(
            value,
            field_name="value",
        )

        return self.window_start <= value < self.window_end


class EnterpriseWorkspaceQuotaLimit(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    limit_version: Literal["enterprise-quota-limit-v1"] = ENTERPRISE_QUOTA_LIMIT_VERSION

    quota_limit_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    dimension: EnterpriseQuotaDimension
    window: EnterpriseQuotaWindow

    limit: int = Field(
        ge=0,
    )


class EnterpriseQuotaAccountingEntry(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    accounting_version: Literal["enterprise-quota-accounting-v1"] = (
        ENTERPRISE_QUOTA_ACCOUNTING_VERSION
    )

    accounting_entry_id: str = Field(
        min_length=1,
        max_length=200,
    )
    accounting_group_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    operation: EnterpriseQuotaOperation
    dimension: EnterpriseQuotaDimension

    quantity: int = Field(
        ge=0,
    )

    window: EnterpriseQuotaWindow
    occurred_at: datetime

    @model_validator(mode="after")
    def require_accounting_integrity(
        self,
    ) -> EnterpriseQuotaAccountingEntry:
        _require_timezone_aware(
            self.occurred_at,
            field_name="occurred_at",
        )

        if not self.window.contains(self.occurred_at):
            raise ValueError("enterprise quota occurred_at must be inside the accounting window")

        allowed_dimensions = _OPERATION_DIMENSIONS[self.operation]

        if self.dimension not in allowed_dimensions:
            raise ValueError("enterprise quota dimension is not valid for the operation")

        return self


def quota_dimensions_for_operation(
    operation: EnterpriseQuotaOperation,
) -> frozenset[EnterpriseQuotaDimension]:
    return _OPERATION_DIMENSIONS[operation]


def _require_timezone_aware(
    value: datetime,
    *,
    field_name: str,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"enterprise quota {field_name} must be timezone-aware")
