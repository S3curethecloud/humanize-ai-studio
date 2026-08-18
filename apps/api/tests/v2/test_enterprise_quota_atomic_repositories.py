from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaAccountingEntry,
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_quota import (
    EnterpriseQuotaAccountingRepository,
    InMemoryEnterpriseQuotaAccountingRepository,
    SQLiteEnterpriseQuotaAccountingRepository,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionOutcome,
    EnterpriseQuotaDecisionService,
)

NOW = datetime(
    2026,
    8,
    13,
    12,
    0,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=NOW,
    window_end=NOW + timedelta(days=1),
)

DECISION_SERVICE = EnterpriseQuotaDecisionService()


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

    raise AssertionError(f"unsupported backend: {backend}")


def _entry(
    *,
    accounting_entry_id: str,
    accounting_group_id: str = "group_test",
    workspace_id: str = "workspace_test",
    operation: EnterpriseQuotaOperation = (EnterpriseQuotaOperation.SINGLE_REWRITE),
    dimension: EnterpriseQuotaDimension = (EnterpriseQuotaDimension.REWRITE_REQUESTS),
    quantity: int = 1,
    window: EnterpriseQuotaWindow = WINDOW,
) -> EnterpriseQuotaAccountingEntry:
    return EnterpriseQuotaAccountingEntry(
        accounting_entry_id=(accounting_entry_id),
        accounting_group_id=(accounting_group_id),
        workspace_id=workspace_id,
        operation=operation,
        dimension=dimension,
        quantity=quantity,
        window=window,
        occurred_at=window.window_start,
    )


def _limit(
    *,
    quota_limit_id: str,
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
def test_atomic_allow_persists_entry(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entry = _entry(
        accounting_entry_id="entry_allow",
        quantity=4,
    )

    result = repository.check_and_consume_group(
        entries=(entry,),
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                limit=10,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is True
    assert len(result.decisions) == 1

    decision = result.decisions[0]

    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW
    assert decision.current_usage == 0
    assert decision.requested_quantity == 4
    assert decision.projected_usage == 4

    assert repository.get("entry_allow") == entry

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 4
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_exact_limit_boundary_persists(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="existing",
            accounting_group_id="existing_group",
            quantity=6,
        )
    )

    result = repository.check_and_consume_group(
        entries=(
            _entry(
                accounting_entry_id="boundary",
                accounting_group_id="boundary_group",
                quantity=4,
            ),
        ),
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                limit=10,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is True
    assert result.decisions[0].current_usage == 6
    assert result.decisions[0].projected_usage == 10

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 10
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_over_limit_writes_nothing(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="existing",
            accounting_group_id="existing_group",
            quantity=7,
        )
    )

    denied = _entry(
        accounting_entry_id="denied",
        accounting_group_id="denied_group",
        quantity=4,
    )

    result = repository.check_and_consume_group(
        entries=(denied,),
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                limit=10,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is False
    assert result.decisions[0].outcome is (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED)
    assert result.decisions[0].current_usage == 7
    assert result.decisions[0].projected_usage == 11

    assert repository.get("denied") is None

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 7
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_missing_limit_is_fail_closed(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entry = _entry(
        accounting_entry_id="no_limit",
        quantity=1,
    )

    result = repository.check_and_consume_group(
        entries=(entry,),
        limits=(),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is False
    assert result.decisions[0].outcome is (EnterpriseQuotaDecisionOutcome.NO_LIMIT_CONFIGURED)

    assert repository.get("no_limit") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_multi_dimension_group_commits_all(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entries = (
        _entry(
            accounting_entry_id="requests",
            accounting_group_id="multi_group",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            quantity=1,
        ),
        _entry(
            accounting_entry_id="input",
            accounting_group_id="multi_group",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            quantity=250,
        ),
    )

    limits = (
        _limit(
            quota_limit_id="limit_requests",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            limit=10,
        ),
        _limit(
            quota_limit_id="limit_input",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            limit=1000,
        ),
    )

    result = repository.check_and_consume_group(
        entries=entries,
        limits=limits,
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is True
    assert all(decision.allowed for decision in result.decisions)

    assert repository.get("requests") is not None
    assert repository.get("input") is not None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_multi_dimension_denial_rolls_back_entire_group(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entries = (
        _entry(
            accounting_entry_id="requests",
            accounting_group_id="rollback_group",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            quantity=1,
        ),
        _entry(
            accounting_entry_id="input",
            accounting_group_id="rollback_group",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            quantity=250,
        ),
    )

    limits = (
        _limit(
            quota_limit_id="limit_requests",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            limit=10,
        ),
        _limit(
            quota_limit_id="limit_input",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            limit=200,
        ),
    )

    result = repository.check_and_consume_group(
        entries=entries,
        limits=limits,
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is False
    assert any(
        decision.outcome is (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED)
        for decision in result.decisions
    )

    assert repository.get("requests") is None
    assert repository.get("input") is None

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 0
    )

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            window=WINDOW,
        )
        == 0
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_partial_limit_set_rolls_back_entire_group(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entries = (
        _entry(
            accounting_entry_id="requests",
            accounting_group_id="partial_policy",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            quantity=1,
        ),
        _entry(
            accounting_entry_id="input",
            accounting_group_id="partial_policy",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            quantity=50,
        ),
    )

    result = repository.check_and_consume_group(
        entries=entries,
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
                limit=10,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is False
    assert any(
        decision.outcome is (EnterpriseQuotaDecisionOutcome.NO_LIMIT_CONFIGURED)
        for decision in result.decisions
    )

    assert repository.get("requests") is None
    assert repository.get("input") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_decision_order_is_deterministic(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entries = (
        _entry(
            accounting_entry_id="requests",
            accounting_group_id="ordered_group",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            quantity=1,
        ),
        _entry(
            accounting_entry_id="input",
            accounting_group_id="ordered_group",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            quantity=10,
        ),
    )

    result = repository.check_and_consume_group(
        entries=entries,
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
                limit=10,
            ),
            _limit(
                quota_limit_id="limit_input",
                dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
                limit=100,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert tuple(decision.dimension for decision in result.decisions) == (
        EnterpriseQuotaDimension.INPUT_CHARACTERS,
        EnterpriseQuotaDimension.REWRITE_REQUESTS,
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_existing_accounting_group_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="existing",
            accounting_group_id="reused_group",
        )
    )

    with pytest.raises(
        ValueError,
        match="accounting group already exists",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="new",
                    accounting_group_id="reused_group",
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="limit_requests",
                ),
            ),
            decision_service=DECISION_SERVICE,
        )

    assert repository.get("new") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_existing_entry_id_is_rejected_without_partial_write(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    repository.create(
        _entry(
            accounting_entry_id="collision",
            accounting_group_id="old_group",
        )
    )

    with pytest.raises(
        ValueError,
        match="accounting entry already exists",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="collision",
                    accounting_group_id="new_group",
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="limit_requests",
                ),
            ),
            decision_service=DECISION_SERVICE,
        )

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 1
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_empty_atomic_group_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="group must not be empty",
    ):
        repository.check_and_consume_group(
            entries=(),
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_entry_ids_in_group_are_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entries = (
        _entry(
            accounting_entry_id="duplicate",
            accounting_group_id="dup_group",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        ),
        _entry(
            accounting_entry_id="duplicate",
            accounting_group_id="dup_group",
            dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
        ),
    )

    with pytest.raises(
        ValueError,
        match="duplicate entry ids",
    ):
        repository.check_and_consume_group(
            entries=entries,
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_dimensions_in_group_are_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    entries = (
        _entry(
            accounting_entry_id="one",
            accounting_group_id="dup_dimension",
        ),
        _entry(
            accounting_entry_id="two",
            accounting_group_id="dup_dimension",
        ),
    )

    with pytest.raises(
        ValueError,
        match="duplicate dimensions",
    ):
        repository.check_and_consume_group(
            entries=entries,
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_mixed_workspace_group_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="one workspace",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="one",
                    accounting_group_id="mixed_workspace",
                    workspace_id="workspace_test",
                    dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
                ),
                _entry(
                    accounting_entry_id="two",
                    accounting_group_id="mixed_workspace",
                    workspace_id="workspace_other",
                    dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
                ),
            ),
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_mixed_accounting_group_ids_are_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="one accounting_group_id",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="one",
                    accounting_group_id="group_one",
                    dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
                ),
                _entry(
                    accounting_entry_id="two",
                    accounting_group_id="group_two",
                    dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
                ),
            ),
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_mixed_operation_group_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="one operation",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="one",
                    accounting_group_id="mixed_operation",
                    operation=(EnterpriseQuotaOperation.SINGLE_REWRITE),
                    dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
                ),
                _entry(
                    accounting_entry_id="two",
                    accounting_group_id="mixed_operation",
                    operation=(EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE),
                    dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
                ),
            ),
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_mixed_window_group_is_rejected(
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

    with pytest.raises(
        ValueError,
        match="one window",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="one",
                    accounting_group_id="mixed_window",
                    window=WINDOW,
                    dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
                ),
                _entry(
                    accounting_entry_id="two",
                    accounting_group_id="mixed_window",
                    window=next_window,
                    dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
                ),
            ),
            limits=(),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_limits_are_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="duplicate limits",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="entry",
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="limit_one",
                ),
                _limit(
                    quota_limit_id="limit_two",
                ),
            ),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_limit_for_unrequested_dimension_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="unrequested dimension",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="entry",
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="limit_input",
                    dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
                ),
            ),
            decision_service=DECISION_SERVICE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_limit_scope_mismatch_writes_nothing(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="workspace does not match",
    ):
        repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id="entry",
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="bad_limit",
                    workspace_id="workspace_other",
                ),
            ),
            decision_service=DECISION_SERVICE,
        )

    assert repository.get("entry") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_concurrent_consumers_cannot_oversubscribe_limit(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    barrier = Barrier(2)

    def consume(
        suffix: str,
    ) -> bool:
        barrier.wait()

        result = repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id=(f"entry_{suffix}"),
                    accounting_group_id=(f"group_{suffix}"),
                    quantity=6,
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="limit_requests",
                    limit=10,
                ),
            ),
            decision_service=DECISION_SERVICE,
        )

        return result.consumed

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                consume,
                ("one", "two"),
            )
        )

    assert sorted(results) == [
        False,
        True,
    ]

    assert (
        repository.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 6
    )


def test_sqlite_atomic_commit_survives_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    first = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    result = first.check_and_consume_group(
        entries=(
            _entry(
                accounting_entry_id="restart",
                accounting_group_id="restart_group",
                quantity=5,
            ),
        ),
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                limit=10,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is True

    second = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    assert second.get("restart") is not None

    assert (
        second.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 5
    )


def test_sqlite_denied_group_remains_absent_after_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    first = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    result = first.check_and_consume_group(
        entries=(
            _entry(
                accounting_entry_id="denied_restart",
                accounting_group_id="denied_restart_group",
                quantity=11,
            ),
        ),
        limits=(
            _limit(
                quota_limit_id="limit_requests",
                limit=10,
            ),
        ),
        decision_service=DECISION_SERVICE,
    )

    assert result.consumed is False

    second = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=database_path,
    )

    assert second.get("denied_restart") is None

    assert (
        second.sum_usage(
            workspace_id="workspace_test",
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            window=WINDOW,
        )
        == 0
    )


def test_repository_protocol_includes_atomic_authority(
    tmp_path: Path,
) -> None:
    memory: EnterpriseQuotaAccountingRepository = InMemoryEnterpriseQuotaAccountingRepository()

    sqlite: EnterpriseQuotaAccountingRepository = SQLiteEnterpriseQuotaAccountingRepository(
        database_path=tmp_path / "quota.db",
    )

    for repository in (
        memory,
        sqlite,
    ):
        result = repository.check_and_consume_group(
            entries=(
                _entry(
                    accounting_entry_id=(f"entry_{type(repository).__name__}"),
                    accounting_group_id=(f"group_{type(repository).__name__}"),
                ),
            ),
            limits=(
                _limit(
                    quota_limit_id="limit_requests",
                ),
            ),
            decision_service=DECISION_SERVICE,
        )

        assert result.consumed is True
