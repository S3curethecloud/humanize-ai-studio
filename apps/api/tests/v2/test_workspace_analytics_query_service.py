from __future__ import annotations

from tests.v2.test_support_authorization_gate import (
    allow_all_workspace_authorization_gate,
    deny_all_workspace_authorization_gate,
)
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.v2.domain.models import (
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)
from app.v2.domain.observability import (
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.repositories.observability import (
    InMemoryObservabilityEventRepository,
    SQLiteObservabilityEventRepository,
)
from app.v2.services.workspace_analytics_aggregator import (
    WorkspaceAnalyticsAggregator,
)
from app.v2.services.workspace_analytics_query_service import (
    WorkspaceAnalyticsQueryLimitError,
    WorkspaceAnalyticsQueryService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)

START = datetime(
    2026,
    8,
    12,
    0,
    0,
    tzinfo=UTC,
)
END = START + timedelta(days=1)
GENERATED_AT = END + timedelta(minutes=5)


def _event(
    event_id: str,
    *,
    occurred_at: datetime,
    workspace_id: str = "workspace_test",
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> PersistentObservabilityEvent:
    return PersistentObservabilityEvent(
        event_id=event_id,
        workspace_id=workspace_id,
        user_id="user_test",
        operation=(ObservabilityOperation.SINGLE_REWRITE),
        outcome=(ObservabilityOutcome.SUCCEEDED),
        occurred_at=occurred_at,
        duration_ms=10.0,
        input_char_count=100,
        output_char_count=120,
        provider_execution_count=1,
        provider_name="provider-test",
        fallback_used=False,
        token_usage=ObservabilityTokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens),
        ),
        rewrite_history_id=(f"history_{event_id}"),
    )


def _workspace_service(
    *,
    include_membership: bool = True,
) -> WorkspaceService:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()

    users.create(
        UserRecord(
            user_id="user_test",
            email="user@example.com",
            display_name="Test User",
        )
    )

    workspaces.create(
        WorkspaceRecord(
            workspace_id="workspace_test",
            name="Test Workspace",
            created_by_user_id="user_test",
        )
    )

    if include_membership:
        memberships.create(
            WorkspaceMembership(
                workspace_id="workspace_test",
                user_id="user_test",
                role=WorkspaceRole.OWNER,
            )
        )

    return WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )


def _service(
    repository: (InMemoryObservabilityEventRepository | SQLiteObservabilityEventRepository),
    *,
    event_limit: int = 1000,
    include_membership: bool = True,
    authorization_gate=None,
) -> WorkspaceAnalyticsQueryService:
    return WorkspaceAnalyticsQueryService(
        repository=repository,
        aggregator=WorkspaceAnalyticsAggregator(
            clock=lambda: GENERATED_AT,
        ),
        event_limit=event_limit,
        authorization_gate=(
            authorization_gate
            or allow_all_workspace_authorization_gate()
        ),
    )


def test_queries_persisted_events_and_aggregates() -> None:
    repository = InMemoryObservabilityEventRepository()

    repository.create(
        _event(
            "event_1",
            occurred_at=START,
            input_tokens=10,
            output_tokens=5,
        )
    )
    repository.create(
        _event(
            "event_2",
            occurred_at=(START + timedelta(hours=1)),
            input_tokens=20,
            output_tokens=7,
        )
    )

    snapshot = _service(repository).query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert snapshot.workspace_id == ("workspace_test")
    assert snapshot.period_start == START
    assert snapshot.period_end == END
    assert snapshot.generated_at == GENERATED_AT

    assert snapshot.event_count == 2
    assert snapshot.succeeded_count == 2
    assert snapshot.total_input_tokens == 30
    assert snapshot.total_output_tokens == 12
    assert snapshot.total_tokens == 42


def test_empty_persisted_window_returns_zero_snapshot() -> None:
    repository = InMemoryObservabilityEventRepository()

    snapshot = _service(repository).query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert snapshot.event_count == 0
    assert snapshot.total_tokens == 0
    assert len(snapshot.operations) == 3


def test_membership_is_required_before_query() -> None:
    repository = InMemoryObservabilityEventRepository()

    repository.create(
        _event(
            "event_private",
            occurred_at=START,
        )
    )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        _service(
            repository,
            include_membership=False,
            authorization_gate=deny_all_workspace_authorization_gate(),
        ).query(
            workspace_id="workspace_test",
            user_id="user_test",
            period_start=START,
            period_end=END,
        )


class _RepositorySpy:
    def __init__(self) -> None:
        self.calls: list[
            tuple[
                str,
                datetime,
                datetime,
                int,
            ]
        ] = []

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
    ]:
        self.calls.append(
            (
                workspace_id,
                period_start,
                period_end,
                limit,
            )
        )

        return ()


def test_queries_with_limit_plus_one_sentinel() -> None:
    repository = _RepositorySpy()

    service = WorkspaceAnalyticsQueryService(
        repository=repository,
        aggregator=WorkspaceAnalyticsAggregator(
            clock=lambda: GENERATED_AT,
        ),
        event_limit=25,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    service.query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert repository.calls == [
        (
            "workspace_test",
            START,
            END,
            26,
        )
    ]


def test_exact_event_limit_is_accepted() -> None:
    repository = InMemoryObservabilityEventRepository()

    for index in range(3):
        repository.create(
            _event(
                f"event_{index}",
                occurred_at=(START + timedelta(minutes=index)),
            )
        )

    snapshot = _service(
        repository,
        event_limit=3,
    ).query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert snapshot.event_count == 3


def test_event_limit_overflow_fails_closed() -> None:
    repository = InMemoryObservabilityEventRepository()

    for index in range(4):
        repository.create(
            _event(
                f"event_{index}",
                occurred_at=(START + timedelta(minutes=index)),
            )
        )

    with pytest.raises(
        WorkspaceAnalyticsQueryLimitError,
        match="narrow the query window",
    ):
        _service(
            repository,
            event_limit=3,
        ).query(
            workspace_id="workspace_test",
            user_id="user_test",
            period_start=START,
            period_end=END,
        )


def test_repository_window_remains_half_open() -> None:
    repository = InMemoryObservabilityEventRepository()

    repository.create(
        _event(
            "event_start",
            occurred_at=START,
        )
    )
    repository.create(
        _event(
            "event_end",
            occurred_at=END,
        )
    )

    snapshot = _service(repository).query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert snapshot.event_count == 1


def test_cross_workspace_events_are_not_aggregated() -> None:
    repository = InMemoryObservabilityEventRepository()

    repository.create(
        _event(
            "event_local",
            occurred_at=START,
        )
    )
    repository.create(
        _event(
            "event_other",
            occurred_at=START,
            workspace_id="workspace_other",
        )
    )

    snapshot = _service(repository).query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert snapshot.event_count == 1


def test_invalid_window_propagates_repository_validation() -> None:
    repository = InMemoryObservabilityEventRepository()

    with pytest.raises(
        ValueError,
        match="period_end must be after",
    ):
        _service(repository).query(
            workspace_id="workspace_test",
            user_id="user_test",
            period_start=END,
            period_end=START,
        )


def test_naive_window_propagates_repository_validation() -> None:
    repository = InMemoryObservabilityEventRepository()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        _service(repository).query(
            workspace_id="workspace_test",
            user_id="user_test",
            period_start=datetime(
                2026,
                8,
                12,
            ),
            period_end=END,
        )


def test_invalid_event_limit_rejected_at_construction() -> None:
    repository = InMemoryObservabilityEventRepository()

    with pytest.raises(
        ValueError,
        match="event_limit must be at least 1",
    ):
        _service(
            repository,
            event_limit=0,
        )


def test_sqlite_persisted_events_are_queryable_after_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "analytics-query.sqlite3"

    writer = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    writer.create(
        _event(
            "event_sqlite",
            occurred_at=START,
            input_tokens=14,
            output_tokens=9,
        )
    )

    reader = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    snapshot = _service(reader).query(
        workspace_id="workspace_test",
        user_id="user_test",
        period_start=START,
        period_end=END,
    )

    assert snapshot.event_count == 1
    assert snapshot.total_tokens == 23
