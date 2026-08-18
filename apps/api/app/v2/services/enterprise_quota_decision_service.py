from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)


class EnterpriseQuotaDecisionOutcome(StrEnum):
    ALLOW = "allow"
    DENY_LIMIT_EXCEEDED = "deny_limit_exceeded"
    NO_LIMIT_CONFIGURED = "no_limit_configured"


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseQuotaDecisionEvidence:
    workspace_id: str
    dimension: EnterpriseQuotaDimension
    window: EnterpriseQuotaWindow

    quota_limit_id: str | None
    configured_limit: int | None

    current_usage: int
    requested_quantity: int
    projected_usage: int

    outcome: EnterpriseQuotaDecisionOutcome

    @property
    def allowed(self) -> bool:
        return self.outcome is EnterpriseQuotaDecisionOutcome.ALLOW


class EnterpriseQuotaDecisionService:
    def evaluate(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
        limit: EnterpriseWorkspaceQuotaLimit | None,
        current_usage: int,
        requested_quantity: int,
    ) -> EnterpriseQuotaDecisionEvidence:
        _require_workspace_id(workspace_id)
        _require_non_negative_integer(
            current_usage,
            field_name="current_usage",
        )
        _require_non_negative_integer(
            requested_quantity,
            field_name="requested_quantity",
        )

        projected_usage = current_usage + requested_quantity

        if limit is None:
            return EnterpriseQuotaDecisionEvidence(
                workspace_id=workspace_id,
                dimension=dimension,
                window=window,
                quota_limit_id=None,
                configured_limit=None,
                current_usage=current_usage,
                requested_quantity=requested_quantity,
                projected_usage=projected_usage,
                outcome=(EnterpriseQuotaDecisionOutcome.NO_LIMIT_CONFIGURED),
            )

        _require_limit_scope(
            workspace_id=workspace_id,
            dimension=dimension,
            window=window,
            limit=limit,
        )

        if projected_usage <= limit.limit:
            outcome = EnterpriseQuotaDecisionOutcome.ALLOW
        else:
            outcome = EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED

        return EnterpriseQuotaDecisionEvidence(
            workspace_id=workspace_id,
            dimension=dimension,
            window=window,
            quota_limit_id=limit.quota_limit_id,
            configured_limit=limit.limit,
            current_usage=current_usage,
            requested_quantity=requested_quantity,
            projected_usage=projected_usage,
            outcome=outcome,
        )


def _require_workspace_id(
    workspace_id: str,
) -> None:
    if not workspace_id:
        raise ValueError("enterprise quota decision workspace_id must not be empty")


def _require_non_negative_integer(
    value: int,
    *,
    field_name: str,
) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"enterprise quota decision {field_name} must be an integer")

    if value < 0:
        raise ValueError(f"enterprise quota decision {field_name} must be non-negative")


def _require_limit_scope(
    *,
    workspace_id: str,
    dimension: EnterpriseQuotaDimension,
    window: EnterpriseQuotaWindow,
    limit: EnterpriseWorkspaceQuotaLimit,
) -> None:
    if limit.workspace_id != workspace_id:
        raise ValueError("enterprise quota limit workspace does not match decision workspace")

    if limit.dimension != dimension:
        raise ValueError("enterprise quota limit dimension does not match decision dimension")

    if not _windows_match(
        limit.window,
        window,
    ):
        raise ValueError("enterprise quota limit window does not match decision window")


def _windows_match(
    left: EnterpriseQuotaWindow,
    right: EnterpriseQuotaWindow,
) -> bool:
    return left.window_start == right.window_start and left.window_end == right.window_end
