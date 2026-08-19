from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.v2.domain.observability import (
    PersistentObservabilityEvent,
    WorkspaceAnalyticsSnapshot,
)
from app.v2.services.workspace_analytics_aggregator import (
    WorkspaceAnalyticsAggregator,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


class WorkspaceAnalyticsEventReader(Protocol):
    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        PersistentObservabilityEvent,
        ...,
    ]: ...


class WorkspaceAnalyticsQueryLimitError(RuntimeError):
    pass


class WorkspaceAnalyticsQueryService:
    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        repository: WorkspaceAnalyticsEventReader,
        aggregator: WorkspaceAnalyticsAggregator,
        authorization_gate: WorkspaceAuthorizationGate | None = None,
        event_limit: int = 1000,
    ) -> None:
        if event_limit < 1:
            raise ValueError("workspace analytics event_limit must be at least 1")

        self._workspace_service = workspace_service
        self._repository = repository
        self._aggregator = aggregator
        self._authorization_gate = authorization_gate
        self._event_limit = event_limit

    def query(
        self,
        *,
        workspace_id: str,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> WorkspaceAnalyticsSnapshot:
        if self._authorization_gate is not None:
            self._authorization_gate.require(
                workspace_id=workspace_id,
                user_id=user_id,
                permission=EnterprisePermission.ANALYTICS_READ,
            )
        else:
            self._workspace_service.require_membership(
                workspace_id=workspace_id,
                user_id=user_id,
            )

        events = self._repository.list_for_workspace(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            limit=self._event_limit + 1,
        )

        if len(events) > self._event_limit:
            raise WorkspaceAnalyticsQueryLimitError(
                "workspace analytics event limit exceeded; narrow the query window"
            )

        return self._aggregator.aggregate(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            events=events,
        )
