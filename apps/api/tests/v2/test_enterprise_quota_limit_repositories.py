from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import (
    UTC,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from threading import Barrier

import pytest

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)

NOW = datetime(
    2026,
    8,
    13,
    16,
    0,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=NOW,
    window_end=NOW + timedelta(days=1),
)


def _repository(
    *,
    backend: str,
    database_path: Path,
) -> EnterpriseQuotaLimitRepository:
    if backend == "memory":
        return InMemoryEnterpriseQuotaLimitRepository()

    if backend == "sqlite":
        return SQLiteEnterpriseQuotaLimitRepository(
            database_path=database_path,
        )

    raise AssertionError(f"unsupported backend: {backend}")


def _limit(
    *,
    quota_limit_id: str = "limit_test",
    workspace_id: str = "workspace_test",
    dimension: EnterpriseQuotaDimension = (EnterpriseQuotaDimension.REWRITE_REQUESTS),
    window: EnterpriseQuotaWindow = WINDOW,
    limit: int = 10,
) -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id=quota_limit_id,
        workspace_id=workspace_id,
        dimension=dimension,
        window=window,
        limit=limit,
    )


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

    quota_limit = _limit()

    assert repository.create(quota_limit) == quota_limit
    assert repository.get(quota_limit.quota_limit_id) == quota_limit


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_get_unknown_returns_none(
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
def test_duplicate_limit_id_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    first = _limit(
        quota_limit_id="duplicate",
    )

    repository.create(first)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(
            _limit(
                quota_limit_id="duplicate",
                workspace_id="workspace_other",
            )
        )

    assert repository.get("duplicate") == first


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_exact_same_scope_window_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="first",
        )
    )

    with pytest.raises(
        ValueError,
        match="overlaps existing authority",
    ):
        repository.create(
            _limit(
                quota_limit_id="second",
            )
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_partial_overlap_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="first",
        )
    )

    overlap = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start + timedelta(hours=12)),
        window_end=(WINDOW.window_end + timedelta(hours=12)),
    )

    with pytest.raises(
        ValueError,
        match="overlaps existing authority",
    ):
        repository.create(
            _limit(
                quota_limit_id="second",
                window=overlap,
            )
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_contained_overlap_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="outer",
        )
    )

    contained = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start + timedelta(hours=1)),
        window_end=(WINDOW.window_end - timedelta(hours=1)),
    )

    with pytest.raises(
        ValueError,
        match="overlaps existing authority",
    ):
        repository.create(
            _limit(
                quota_limit_id="inner",
                window=contained,
            )
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_adjacent_windows_are_allowed(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    first = _limit(
        quota_limit_id="first",
    )

    second_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=(WINDOW.window_end + timedelta(days=1)),
    )

    second = _limit(
        quota_limit_id="second",
        window=second_window,
    )

    repository.create(first)
    repository.create(second)

    assert repository.get("first") == first
    assert repository.get("second") == second


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_overlap_is_allowed_for_different_workspace(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="first",
            workspace_id="workspace_one",
        )
    )

    second = _limit(
        quota_limit_id="second",
        workspace_id="workspace_two",
    )

    repository.create(second)

    assert repository.get("second") == second


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_overlap_is_allowed_for_different_dimension(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="requests",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        )
    )

    second = _limit(
        quota_limit_id="input",
        dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
    )

    repository.create(second)

    assert repository.get("input") == second


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_exact_returns_authoritative_limit(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    quota_limit = _limit(
        quota_limit_id="authoritative",
    )

    repository.create(quota_limit)

    assert (
        repository.resolve_exact(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == quota_limit
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_exact_missing_returns_none(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    assert (
        repository.resolve_exact(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        is None
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_exact_requires_full_window_identity(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="stored",
        )
    )

    subset = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start + timedelta(hours=1)),
        window_end=WINDOW.window_end,
    )

    assert (
        repository.resolve_exact(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=subset,
        )
        is None
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_equivalent_timezone_window_resolves(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    quota_limit = _limit(
        quota_limit_id="timezone",
    )

    repository.create(quota_limit)

    offset = timezone(timedelta(hours=-7))

    equivalent = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start.astimezone(offset)),
        window_end=(WINDOW.window_end.astimezone(offset)),
    )

    assert (
        repository.resolve_exact(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=equivalent,
        )
        == quota_limit
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_equivalent_timezone_overlap_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="first",
        )
    )

    offset = timezone(timedelta(hours=5, minutes=30))

    equivalent = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start.astimezone(offset)),
        window_end=(WINDOW.window_end.astimezone(offset)),
    )

    with pytest.raises(
        ValueError,
        match="overlaps existing authority",
    ):
        repository.create(
            _limit(
                quota_limit_id="second",
                window=equivalent,
            )
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_list_is_workspace_and_dimension_scoped(
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

    included_one = _limit(
        quota_limit_id="included_one",
    )

    included_two = _limit(
        quota_limit_id="included_two",
        window=next_window,
    )

    repository.create(included_two)
    repository.create(included_one)

    repository.create(
        _limit(
            quota_limit_id="other_workspace",
            workspace_id="workspace_other",
        )
    )

    repository.create(
        _limit(
            quota_limit_id="other_dimension",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
        )
    )

    assert repository.list_for_workspace_dimension(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
    ) == (
        included_one,
        included_two,
    )


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

    second_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=(WINDOW.window_end + timedelta(days=1)),
    )

    third_window = EnterpriseQuotaWindow(
        window_start=second_window.window_end,
        window_end=(second_window.window_end + timedelta(days=1)),
    )

    limits = (
        _limit(
            quota_limit_id="third",
            window=third_window,
        ),
        _limit(
            quota_limit_id="first",
            window=WINDOW,
        ),
        _limit(
            quota_limit_id="second",
            window=second_window,
        ),
    )

    for quota_limit in limits:
        repository.create(quota_limit)

    assert tuple(
        quota_limit.quota_limit_id
        for quota_limit in repository.list_for_workspace_dimension(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        )
    ) == (
        "first",
        "second",
        "third",
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

    repository.create(
        _limit(
            quota_limit_id="first",
        )
    )

    next_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=(WINDOW.window_end + timedelta(days=1)),
    )

    repository.create(
        _limit(
            quota_limit_id="second",
            window=next_window,
        )
    )

    result = repository.list_for_workspace_dimension(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        limit=1,
    )

    assert tuple(quota_limit.quota_limit_id for quota_limit in result) == ("first",)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
@pytest.mark.parametrize(
    "list_limit",
    (0, 10001),
)
def test_invalid_list_limit_is_rejected(
    backend: str,
    list_limit: int,
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
        repository.list_for_workspace_dimension(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            limit=list_limit,
        )


def test_sqlite_limit_survives_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    first = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )

    quota_limit = _limit(
        quota_limit_id="restart",
    )

    first.create(quota_limit)

    second = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )

    assert second.get("restart") == quota_limit

    assert (
        second.resolve_exact(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == quota_limit
    )


def test_sqlite_limit_table_is_separate_from_accounting(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )

    import sqlite3

    with sqlite3.connect(str(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert "enterprise_quota_limits" in tables

    assert "enterprise_quota_accounting" not in tables


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_concurrent_overlapping_limit_creation_has_one_winner(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    barrier = Barrier(2)

    def create_limit(
        suffix: str,
    ) -> bool:
        barrier.wait()

        try:
            repository.create(
                _limit(
                    quota_limit_id=(f"limit_{suffix}"),
                )
            )
        except ValueError:
            return False

        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                create_limit,
                ("one", "two"),
            )
        )

    assert sorted(results) == [
        False,
        True,
    ]

    stored = repository.list_for_workspace_dimension(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
    )

    assert len(stored) == 1


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_returns_active_authoritative_limit(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    quota_limit = _limit(
        quota_limit_id="active",
    )
    repository.create(quota_limit)

    assert (
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=WINDOW.window_start + timedelta(hours=1),
        )
        == quota_limit
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_includes_window_start(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    quota_limit = _limit(
        quota_limit_id="window_start",
    )
    repository.create(quota_limit)

    assert (
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=WINDOW.window_start,
        )
        == quota_limit
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_excludes_window_end(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="window_end",
        )
    )

    assert (
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=WINDOW.window_end,
        )
        is None
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_boundary_selects_adjacent_window(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    next_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=WINDOW.window_end + timedelta(days=1),
    )

    repository.create(
        _limit(
            quota_limit_id="first",
        )
    )

    second = _limit(
        quota_limit_id="second",
        window=next_window,
    )
    repository.create(second)

    assert (
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=WINDOW.window_end,
        )
        == second
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_equivalent_timezone_resolves(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    quota_limit = _limit(
        quota_limit_id="timezone_active",
    )
    repository.create(quota_limit)

    offset = timezone(timedelta(hours=-7))
    occurred_at = (
        WINDOW.window_start + timedelta(hours=1)
    ).astimezone(offset)

    assert (
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=occurred_at,
        )
        == quota_limit
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_missing_returns_none(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    assert (
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=WINDOW.window_start,
        )
        is None
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolve_at_rejects_naive_timestamp(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _limit(
            quota_limit_id="timezone_required",
        )
    )

    with pytest.raises(
        ValueError,
        match="timestamps must be timezone-aware",
    ):
        repository.resolve_at(
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            occurred_at=datetime(
                2026,
                8,
                13,
                17,
                0,
            ),
        )


def test_repository_protocol_shape(
    tmp_path: Path,
) -> None:
    memory: EnterpriseQuotaLimitRepository = InMemoryEnterpriseQuotaLimitRepository()

    sqlite: EnterpriseQuotaLimitRepository = SQLiteEnterpriseQuotaLimitRepository(
        database_path=tmp_path / "quota.db",
    )

    for repository in (
        memory,
        sqlite,
    ):
        quota_limit = _limit(
            quota_limit_id=(f"limit_{type(repository).__name__}"),
        )

        repository.create(quota_limit)

        assert repository.get(quota_limit.quota_limit_id) == quota_limit

        assert (
            repository.resolve_exact(
                workspace_id=(quota_limit.workspace_id),
                dimension=(quota_limit.dimension),
                window=quota_limit.window,
            )
            == quota_limit
        )

        assert (
            repository.resolve_at(
                workspace_id=(quota_limit.workspace_id),
                dimension=(quota_limit.dimension),
                occurred_at=quota_limit.window.window_start,
            )
            == quota_limit
        )
