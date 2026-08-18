from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)
from app.v2.repositories.enterprise_admin_audit import (
    EnterpriseAdminAuditRepository,
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
)

BASE_TIME = datetime(
    2026,
    8,
    15,
    tzinfo=UTC,
)


def _event(
    *,
    audit_event_id: str,
    workspace_id: str = "workspace_1",
    actor_user_id: str = "user_1",
    occurred_at: datetime = BASE_TIME,
) -> EnterpriseAdminAuditEvent:
    return EnterpriseAdminAuditEvent(
        audit_event_id=audit_event_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
        ),
        outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
        target_type="quota_limit",
        target_id="limit_requests",
        occurred_at=occurred_at,
    )


def _repositories(
    tmp_path: Path,
) -> tuple[
    EnterpriseAdminAuditRepository,
    EnterpriseAdminAuditRepository,
]:
    return (
        InMemoryEnterpriseAdminAuditRepository(),
        SQLiteEnterpriseAdminAuditRepository(
            database_path=tmp_path / "audit.db",
        ),
    )


def test_create_and_get_round_trip(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        event = _event(
            audit_event_id="audit_1",
        )

        assert repository.create(event) == event
        assert repository.get("audit_1") == event


def test_get_missing_returns_none(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        assert repository.get("missing") is None


def test_duplicate_event_id_is_rejected(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        event = _event(
            audit_event_id="audit_1",
        )

        repository.create(event)

        with pytest.raises(
            ValueError,
            match="already exists",
        ):
            repository.create(event)


def test_list_is_workspace_scoped(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        repository.create(
            _event(
                audit_event_id="audit_1",
            )
        )
        repository.create(
            _event(
                audit_event_id="audit_2",
                workspace_id="workspace_2",
            )
        )

        events = repository.list_for_workspace(
            workspace_id="workspace_1",
            period_start=BASE_TIME - timedelta(days=1),
            period_end=BASE_TIME + timedelta(days=1),
        )

        assert tuple(
            event.audit_event_id
            for event in events
        ) == ("audit_1",)


def test_list_uses_half_open_time_window(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        repository.create(
            _event(
                audit_event_id="start",
                occurred_at=BASE_TIME,
            )
        )
        repository.create(
            _event(
                audit_event_id="middle",
                occurred_at=(
                    BASE_TIME + timedelta(hours=1)
                ),
            )
        )
        repository.create(
            _event(
                audit_event_id="end",
                occurred_at=(
                    BASE_TIME + timedelta(hours=2)
                ),
            )
        )

        events = repository.list_for_workspace(
            workspace_id="workspace_1",
            period_start=BASE_TIME,
            period_end=(
                BASE_TIME + timedelta(hours=2)
            ),
        )

        assert tuple(
            event.audit_event_id
            for event in events
        ) == (
            "start",
            "middle",
        )


def test_list_is_deterministically_ordered(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        repository.create(
            _event(
                audit_event_id="audit_b",
            )
        )
        repository.create(
            _event(
                audit_event_id="audit_a",
            )
        )

        events = repository.list_for_workspace(
            workspace_id="workspace_1",
            period_start=BASE_TIME - timedelta(days=1),
            period_end=BASE_TIME + timedelta(days=1),
        )

        assert tuple(
            event.audit_event_id
            for event in events
        ) == (
            "audit_a",
            "audit_b",
        )


def test_list_limit_is_enforced(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        repository.create(
            _event(
                audit_event_id="audit_a",
            )
        )
        repository.create(
            _event(
                audit_event_id="audit_b",
            )
        )

        events = repository.list_for_workspace(
            workspace_id="workspace_1",
            period_start=BASE_TIME - timedelta(days=1),
            period_end=BASE_TIME + timedelta(days=1),
            limit=1,
        )

        assert len(events) == 1


@pytest.mark.parametrize(
    "limit",
    [
        0,
        10001,
    ],
)
def test_invalid_list_limit_is_rejected(
    tmp_path: Path,
    limit: int,
) -> None:
    for repository in _repositories(tmp_path):
        with pytest.raises(
            ValueError,
            match="between 1 and 10000",
        ):
            repository.list_for_workspace(
                workspace_id="workspace_1",
                period_start=(
                    BASE_TIME - timedelta(days=1)
                ),
                period_end=(
                    BASE_TIME + timedelta(days=1)
                ),
                limit=limit,
            )


def test_invalid_query_window_is_rejected(
    tmp_path: Path,
) -> None:
    for repository in _repositories(tmp_path):
        with pytest.raises(
            ValueError,
            match="must be after",
        ):
            repository.list_for_workspace(
                workspace_id="workspace_1",
                period_start=BASE_TIME,
                period_end=BASE_TIME,
            )


def test_naive_query_timestamp_is_rejected(
    tmp_path: Path,
) -> None:
    naive = datetime(
        2026,
        8,
        15,
    )

    for repository in _repositories(tmp_path):
        with pytest.raises(
            ValueError,
            match="must be timezone-aware",
        ):
            repository.list_for_workspace(
                workspace_id="workspace_1",
                period_start=naive,
                period_end=(
                    naive + timedelta(days=1)
                ),
            )


def test_sqlite_persists_across_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "audit.db"

    first = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    first.create(
        _event(
            audit_event_id="audit_1",
        )
    )

    second = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )

    assert second.get("audit_1") == _event(
        audit_event_id="audit_1",
    )
