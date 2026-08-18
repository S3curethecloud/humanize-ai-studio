from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaAccountingEntry,
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
)
from app.v2.repositories.enterprise_quota import (
    EnterpriseQuotaAccountingRepository,
    InMemoryEnterpriseQuotaAccountingRepository,
    SQLiteEnterpriseQuotaAccountingRepository,
)

NOW = datetime(
    2026,
    8,
    13,
    8,
    0,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=NOW,
    window_end=NOW + timedelta(days=1),
)


def _entry(
    *,
    accounting_entry_id: str = "entry_test",
    accounting_group_id: str = "group_test",
    workspace_id: str = "workspace_test",
    operation: EnterpriseQuotaOperation = (EnterpriseQuotaOperation.SINGLE_REWRITE),
    dimension: EnterpriseQuotaDimension = (EnterpriseQuotaDimension.REWRITE_REQUESTS),
    quantity: int = 1,
    window: EnterpriseQuotaWindow = WINDOW,
    occurred_at: datetime = NOW,
) -> EnterpriseQuotaAccountingEntry:
    return EnterpriseQuotaAccountingEntry(
        accounting_entry_id=accounting_entry_id,
        accounting_group_id=accounting_group_id,
        workspace_id=workspace_id,
        operation=operation,
        dimension=dimension,
        quantity=quantity,
        window=window,
        occurred_at=occurred_at,
    )


def _repository(
    *,
    backend: str,
    database_path: Path,
) -> EnterpriseQuotaAccountingRepository:
    if backend == "memory":
        return InMemoryEnterpriseQuotaAccountingRepository()

    if backend == "sqlite":
        return SQLiteEnterpriseQuotaAccountingRepository(
            database_path=database_path,
        )

    raise AssertionError(f"unsupported test backend: {backend}")


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_create_and_get_round_trip(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entry = _entry()

    assert repository.create(entry) == entry
    assert repository.get(entry.accounting_entry_id) == entry


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_get_unknown_entry_returns_none(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    assert repository.get("missing") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_entry_id_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    first = _entry(
        accounting_entry_id="entry_duplicate",
    )
    second = _entry(
        accounting_entry_id="entry_duplicate",
        accounting_group_id="group_other",
        quantity=9,
    )

    repository.create(first)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(second)

    assert repository.get("entry_duplicate") == first


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_list_is_workspace_dimension_and_window_scoped(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    next_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=(WINDOW.window_end + timedelta(days=1)),
    )

    included = _entry(
        accounting_entry_id="included",
        quantity=3,
    )
    other_workspace = _entry(
        accounting_entry_id="other_workspace",
        workspace_id="workspace_other",
    )
    other_dimension = _entry(
        accounting_entry_id="other_dimension",
        operation=(EnterpriseQuotaOperation.SINGLE_REWRITE),
        dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
        quantity=100,
    )
    other_window = _entry(
        accounting_entry_id="other_window",
        window=next_window,
        occurred_at=next_window.window_start,
    )

    for entry in (
        included,
        other_workspace,
        other_dimension,
        other_window,
    ):
        repository.create(entry)

    assert (
        repository.list_for_workspace_dimension_window(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
    ) == (included,)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_list_order_is_deterministic(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    late = _entry(
        accounting_entry_id="entry_late",
        occurred_at=NOW + timedelta(hours=2),
    )
    same_time_b = _entry(
        accounting_entry_id="entry_b",
        occurred_at=NOW + timedelta(hours=1),
    )
    same_time_a = _entry(
        accounting_entry_id="entry_a",
        occurred_at=NOW + timedelta(hours=1),
    )

    for entry in (
        late,
        same_time_b,
        same_time_a,
    ):
        repository.create(entry)

    listed = repository.list_for_workspace_dimension_window(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        window=WINDOW,
    )

    assert tuple(entry.accounting_entry_id for entry in listed) == (
        "entry_a",
        "entry_b",
        "entry_late",
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_list_limit_is_deterministic(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    for index in range(3):
        repository.create(
            _entry(
                accounting_entry_id=f"entry_{index}",
                occurred_at=(NOW + timedelta(minutes=index)),
            )
        )

    listed = repository.list_for_workspace_dimension_window(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        window=WINDOW,
        limit=2,
    )

    assert tuple(entry.accounting_entry_id for entry in listed) == (
        "entry_0",
        "entry_1",
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
@pytest.mark.parametrize(
    "limit",
    (0, 10001),
)
def test_list_rejects_invalid_limit(
    backend: str,
    limit: int,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="between 1 and 10000",
    ):
        repository.list_for_workspace_dimension_window(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
            limit=limit,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_sum_usage_is_exact_integer_sum(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    for entry in (
        _entry(
            accounting_entry_id="entry_1",
            quantity=1,
        ),
        _entry(
            accounting_entry_id="entry_2",
            quantity=4,
        ),
        _entry(
            accounting_entry_id="entry_3",
            quantity=7,
        ),
    ):
        repository.create(entry)

    usage = repository.sum_usage(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        window=WINDOW,
    )

    assert usage == 12
    assert isinstance(usage, int)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_sum_usage_includes_zero_quantity(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="entry_zero",
            quantity=0,
        )
    )

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 0
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_sum_usage_empty_scope_is_zero(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 0
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_sum_usage_excludes_other_scopes(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    next_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=(WINDOW.window_end + timedelta(days=1)),
    )

    entries = (
        _entry(
            accounting_entry_id="included",
            quantity=5,
        ),
        _entry(
            accounting_entry_id="workspace_other",
            workspace_id="workspace_other",
            quantity=100,
        ),
        _entry(
            accounting_entry_id="dimension_other",
            operation=(EnterpriseQuotaOperation.SINGLE_REWRITE),
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            quantity=100,
        ),
        _entry(
            accounting_entry_id="window_other",
            window=next_window,
            occurred_at=next_window.window_start,
            quantity=100,
        ),
    )

    for entry in entries:
        repository.create(entry)

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 5
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_equivalent_timezone_windows_match(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="entry_timezone",
            quantity=11,
        )
    )

    offset = timezone(timedelta(hours=-7))

    equivalent_window = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start.astimezone(offset)),
        window_end=(WINDOW.window_end.astimezone(offset)),
    )

    listed = repository.list_for_workspace_dimension_window(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        window=equivalent_window,
    )

    assert tuple(entry.accounting_entry_id for entry in listed) == ("entry_timezone",)

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=equivalent_window,
        )
        == 11
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_multiple_operations_can_account_same_dimension(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="single",
            operation=(EnterpriseQuotaOperation.SINGLE_REWRITE),
            quantity=1,
        )
    )
    repository.create(
        _entry(
            accounting_entry_id="multi",
            operation=(EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE),
            quantity=2,
        )
    )
    repository.create(
        _entry(
            accounting_entry_id="long",
            operation=(EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE),
            quantity=3,
        )
    )

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 6
    )


def test_sqlite_survives_repository_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    first = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    entry = _entry(
        accounting_entry_id="entry_restart",
        quantity=17,
    )

    first.create(entry)

    second = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    assert second.get("entry_restart") == entry

    assert (
        second.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 17
    )


def test_sqlite_restart_preserves_deterministic_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    first = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    first.create(
        _entry(
            accounting_entry_id="entry_b",
            occurred_at=NOW + timedelta(hours=1),
        )
    )
    first.create(
        _entry(
            accounting_entry_id="entry_a",
            occurred_at=NOW + timedelta(hours=1),
        )
    )

    second = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    listed = second.list_for_workspace_dimension_window(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        window=WINDOW,
    )

    assert tuple(entry.accounting_entry_id for entry in listed) == (
        "entry_a",
        "entry_b",
    )


def test_sqlite_uses_separate_quota_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    import sqlite3

    connection = sqlite3.connect(str(database_path))

    try:
        table_names = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }
    finally:
        connection.close()

    assert "enterprise_quota_accounting" in table_names
    assert "observability_events" not in table_names


def test_repository_protocol_shapes_are_satisfied(
    tmp_path: Path,
) -> None:
    memory: EnterpriseQuotaAccountingRepository = InMemoryEnterpriseQuotaAccountingRepository()
    sqlite: EnterpriseQuotaAccountingRepository = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=tmp_path / "quota.db",
    )

    assert memory.get("missing") is None
    assert sqlite.get("missing") is None
