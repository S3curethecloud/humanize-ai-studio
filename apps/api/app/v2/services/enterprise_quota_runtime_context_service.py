from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    pre_execution_dimensions_for_operation,
)


class EnterpriseQuotaRuntimeContextResolutionError(RuntimeError):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseQuotaRuntimeContext:
    workspace_id: str
    operation: EnterpriseQuotaOperation
    occurred_at: datetime
    window: EnterpriseQuotaWindow
    accounting_group_id: str


class EnterpriseQuotaRuntimeContextService:
    def __init__(
        self,
        *,
        limits: EnterpriseQuotaLimitRepository,
        clock: Callable[[], datetime] | None = None,
        accounting_group_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._limits = limits
        self._clock = clock or _utc_now
        self._accounting_group_id_factory = (
            accounting_group_id_factory or _new_accounting_group_id
        )

    def resolve(
        self,
        *,
        workspace_id: str,
        operation: EnterpriseQuotaOperation,
    ) -> EnterpriseQuotaRuntimeContext:
        _require_workspace_id(workspace_id)

        occurred_at = self._clock()
        _require_aware_timestamp(occurred_at)

        dimensions = tuple(
            sorted(
                pre_execution_dimensions_for_operation(operation),
                key=lambda dimension: dimension.value,
            )
        )

        resolved_limits = tuple(
            self._resolve_required_limit(
                workspace_id=workspace_id,
                dimension=dimension,
                occurred_at=occurred_at,
            )
            for dimension in dimensions
        )

        window = _require_common_window(
            resolved_limits=resolved_limits,
        )

        accounting_group_id = self._accounting_group_id_factory()
        _require_accounting_group_id(accounting_group_id)

        return EnterpriseQuotaRuntimeContext(
            workspace_id=workspace_id,
            operation=operation,
            occurred_at=occurred_at,
            window=window,
            accounting_group_id=accounting_group_id,
        )

    def _resolve_required_limit(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        occurred_at: datetime,
    ) -> EnterpriseWorkspaceQuotaLimit:
        resolved = self._limits.resolve_at(
            workspace_id=workspace_id,
            dimension=dimension,
            occurred_at=occurred_at,
        )

        if resolved is None:
            raise EnterpriseQuotaRuntimeContextResolutionError(
                "enterprise quota runtime context has no active "
                f"limit for dimension={dimension.value}"
            )

        return resolved


def _require_common_window(
    *,
    resolved_limits: tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ],
) -> EnterpriseQuotaWindow:
    if not resolved_limits:
        raise EnterpriseQuotaRuntimeContextResolutionError(
            "enterprise quota runtime context has no "
            "required quota dimensions"
        )

    authoritative_window = resolved_limits[0].window

    if any(
        not _windows_match(
            authoritative_window,
            resolved.window,
        )
        for resolved in resolved_limits[1:]
    ):
        raise EnterpriseQuotaRuntimeContextResolutionError(
            "enterprise quota runtime limits do not share "
            "one exact quota window"
        )

    return authoritative_window


def _windows_match(
    left: EnterpriseQuotaWindow,
    right: EnterpriseQuotaWindow,
) -> bool:
    return (
        _canonical_datetime(left.window_start)
        == _canonical_datetime(right.window_start)
        and _canonical_datetime(left.window_end)
        == _canonical_datetime(right.window_end)
    )


def _require_workspace_id(
    workspace_id: str,
) -> None:
    if not workspace_id:
        raise ValueError(
            "enterprise quota runtime context workspace_id "
            "must not be empty"
        )


def _require_aware_timestamp(
    value: datetime,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "enterprise quota runtime context timestamp "
            "must be timezone-aware"
        )


def _require_accounting_group_id(
    accounting_group_id: str,
) -> None:
    if not isinstance(accounting_group_id, str):
        raise TypeError(
            "enterprise quota runtime context accounting_group_id "
            "must be a string"
        )

    if not accounting_group_id:
        raise ValueError(
            "enterprise quota runtime context accounting_group_id "
            "must not be empty"
        )


def _canonical_datetime(
    value: datetime,
) -> datetime:
    _require_aware_timestamp(value)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_accounting_group_id() -> str:
    return f"quota_group_{uuid4().hex}"
