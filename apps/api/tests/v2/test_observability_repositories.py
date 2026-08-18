from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import pytest

from app.v2.domain.observability import (
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)
from app.v2.repositories.observability import (
    InMemoryObservabilityEventRepository,
    ObservabilityEventRepository,
    SQLiteObservabilityEventRepository,
)

BASE_TIME = datetime(
    2026,
    8,
    12,
    12,
    0,
    tzinfo=UTC,
)


class RepositoryFactory(Protocol):
    def __call__(
        self,
    ) -> ObservabilityEventRepository: ...


def _event(
    *,
    event_id: str,
    workspace_id: str = "workspace_test",
    user_id: str = "user_test",
    occurred_at: datetime = BASE_TIME,
    operation: ObservabilityOperation = (ObservabilityOperation.SINGLE_REWRITE),
) -> PersistentObservabilityEvent:
    values: dict[str, object] = {
        "event_id": event_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "operation": operation,
        "outcome": ObservabilityOutcome.SUCCEEDED,
        "occurred_at": occurred_at,
        "duration_ms": 10.0,
        "input_char_count": 100,
        "output_char_count": 110,
        "provider_execution_count": 1,
        "provider_name": "test-provider",
        "fallback_used": False,
        "token_usage": ObservabilityTokenUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
    }

    if operation is ObservabilityOperation.MULTI_CANDIDATE_REWRITE:
        values["candidate_count"] = 3
        values["candidate_set_id"] = "candidate_set_test"

    if operation is ObservabilityOperation.LONG_DOCUMENT_REWRITE:
        values["section_count"] = 4
        values["long_document_audit_id"] = "audit_test"

    return PersistentObservabilityEvent(**values)


@pytest.fixture(
    params=("memory", "sqlite"),
)
def repository_factory(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> RepositoryFactory:
    if request.param == "memory":
        return InMemoryObservabilityEventRepository

    database_path = tmp_path / "observability.sqlite3"

    def build_sqlite() -> ObservabilityEventRepository:
        return SQLiteObservabilityEventRepository(
            database_path=database_path,
        )

    return build_sqlite


def test_create_and_get_round_trip_exactly(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    event = _event(event_id="event_round_trip")

    created = repository.create(event)
    stored = repository.get(event.event_id)

    assert created == event
    assert stored == event


def test_get_missing_event_returns_none(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    assert repository.get("event_missing") is None


def test_duplicate_event_id_is_rejected(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    event = _event(event_id="event_duplicate")

    repository.create(event)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(event)


def test_workspace_query_isolated_by_workspace(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _event(
            event_id="event_a",
            workspace_id="workspace_a",
        )
    )

    repository.create(
        _event(
            event_id="event_b",
            workspace_id="workspace_b",
        )
    )

    result = repository.list_for_workspace(
        workspace_id="workspace_a",
        period_start=(BASE_TIME - timedelta(minutes=1)),
        period_end=(BASE_TIME + timedelta(minutes=1)),
    )

    assert tuple(event.event_id for event in result) == ("event_a",)


def test_workspace_query_uses_half_open_time_window(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    start = BASE_TIME
    end = BASE_TIME + timedelta(hours=1)

    repository.create(
        _event(
            event_id="event_before",
            occurred_at=(start - timedelta(seconds=1)),
        )
    )

    repository.create(
        _event(
            event_id="event_start",
            occurred_at=start,
        )
    )

    repository.create(
        _event(
            event_id="event_inside",
            occurred_at=(start + timedelta(minutes=30)),
        )
    )

    repository.create(
        _event(
            event_id="event_end",
            occurred_at=end,
        )
    )

    result = repository.list_for_workspace(
        workspace_id="workspace_test",
        period_start=start,
        period_end=end,
    )

    assert tuple(event.event_id for event in result) == (
        "event_start",
        "event_inside",
    )


def test_workspace_query_is_deterministic_for_equal_timestamps(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _event(
            event_id="event_c",
        )
    )

    repository.create(
        _event(
            event_id="event_a",
        )
    )

    repository.create(
        _event(
            event_id="event_b",
        )
    )

    result = repository.list_for_workspace(
        workspace_id="workspace_test",
        period_start=(BASE_TIME - timedelta(seconds=1)),
        period_end=(BASE_TIME + timedelta(seconds=1)),
    )

    assert tuple(event.event_id for event in result) == (
        "event_a",
        "event_b",
        "event_c",
    )


def test_workspace_query_orders_oldest_to_newest(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _event(
            event_id="event_latest",
            occurred_at=(BASE_TIME + timedelta(minutes=20)),
        )
    )

    repository.create(
        _event(
            event_id="event_earliest",
            occurred_at=BASE_TIME,
        )
    )

    repository.create(
        _event(
            event_id="event_middle",
            occurred_at=(BASE_TIME + timedelta(minutes=10)),
        )
    )

    result = repository.list_for_workspace(
        workspace_id="workspace_test",
        period_start=(BASE_TIME - timedelta(minutes=1)),
        period_end=(BASE_TIME + timedelta(hours=1)),
    )

    assert tuple(event.event_id for event in result) == (
        "event_earliest",
        "event_middle",
        "event_latest",
    )


def test_workspace_query_applies_limit_after_ordering(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    for index in range(5):
        repository.create(
            _event(
                event_id=f"event_{index}",
                occurred_at=(BASE_TIME + timedelta(minutes=index)),
            )
        )

    result = repository.list_for_workspace(
        workspace_id="workspace_test",
        period_start=(BASE_TIME - timedelta(minutes=1)),
        period_end=(BASE_TIME + timedelta(hours=1)),
        limit=2,
    )

    assert tuple(event.event_id for event in result) == (
        "event_0",
        "event_1",
    )


def test_query_rejects_naive_start_timestamp(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        repository.list_for_workspace(
            workspace_id="workspace_test",
            period_start=datetime(
                2026,
                8,
                12,
                12,
                0,
            ),
            period_end=(BASE_TIME + timedelta(hours=1)),
        )


def test_query_rejects_invalid_period(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        ValueError,
        match="period_end",
    ):
        repository.list_for_workspace(
            workspace_id="workspace_test",
            period_start=BASE_TIME,
            period_end=BASE_TIME,
        )


def test_query_rejects_nonpositive_limit(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        ValueError,
        match="at least 1",
    ):
        repository.list_for_workspace(
            workspace_id="workspace_test",
            period_start=BASE_TIME,
            period_end=(BASE_TIME + timedelta(hours=1)),
            limit=0,
        )


def test_repository_supports_all_operation_shapes(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    operations = (
        ObservabilityOperation.SINGLE_REWRITE,
        (ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
        (ObservabilityOperation.LONG_DOCUMENT_REWRITE),
    )

    for index, operation in enumerate(
        operations,
    ):
        event = _event(
            event_id=f"event_{index}",
            operation=operation,
            occurred_at=(BASE_TIME + timedelta(seconds=index)),
        )
        repository.create(event)

        assert repository.get(event.event_id) == event


def test_repository_round_trip_retains_only_frozen_event_schema(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    event = _event(event_id="event_privacy")

    repository.create(event)

    stored = repository.get(event.event_id)

    assert stored is not None

    fields = set(stored.model_dump().keys())

    assert "source_text" not in fields
    assert "rewritten_text" not in fields
    assert "prompt" not in fields
    assert "protected_terms" not in fields
    assert "metadata" not in fields


def test_sqlite_survives_repository_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "persistent-observability.sqlite3"

    first = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    event = _event(event_id="event_restart")

    first.create(event)

    second = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    assert second.get(event.event_id) == event


def test_sqlite_schema_contains_required_indexes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "observability-indexes.sqlite3"

    SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    with sqlite3.connect(str(database_path)) as connection:
        indexes = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA index_list(
                    observability_events
                )
                """
            ).fetchall()
        }

    assert "idx_observability_events_workspace_time" in indexes

    assert "idx_observability_events_workspace_operation_time" in indexes


def test_sqlite_payload_contains_no_raw_document_columns(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "observability-privacy.sqlite3"

    repository = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    repository.create(_event(event_id="event_sqlite_privacy"))

    with sqlite3.connect(str(database_path)) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    observability_events
                )
                """
            ).fetchall()
        }

    assert "source_text" not in columns
    assert "rewritten_text" not in columns
    assert "prompt" not in columns
    assert "protected_terms" not in columns
    assert "metadata" not in columns
