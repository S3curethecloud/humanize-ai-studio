from __future__ import annotations

from collections.abc import Callable
from datetime import (
    UTC,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_runtime_context_service import (
    EnterpriseQuotaRuntimeContextResolutionError,
    EnterpriseQuotaRuntimeContextService,
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
    quota_limit_id: str,
    dimension: EnterpriseQuotaDimension,
    window: EnterpriseQuotaWindow = WINDOW,
    workspace_id: str = "workspace_test",
) -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id=quota_limit_id,
        workspace_id=workspace_id,
        dimension=dimension,
        window=window,
        limit=1000,
    )


def _create_limits(
    *,
    repository: EnterpriseQuotaLimitRepository,
    dimensions: tuple[
        EnterpriseQuotaDimension,
        ...,
    ],
    window: EnterpriseQuotaWindow = WINDOW,
) -> None:
    for dimension in dimensions:
        repository.create(
            _limit(
                quota_limit_id=f"limit_{dimension.value}",
                dimension=dimension,
                window=window,
            )
        )


def _service(
    *,
    repository: EnterpriseQuotaLimitRepository,
    clock: Callable[[], datetime] | None = None,
    accounting_group_id_factory: Callable[[], str] | None = None,
) -> EnterpriseQuotaRuntimeContextService:
    return EnterpriseQuotaRuntimeContextService(
        limits=repository,
        clock=clock or (lambda: NOW + timedelta(hours=1)),
        accounting_group_id_factory=(
            accounting_group_id_factory
            or (lambda: "quota_group_test")
        ),
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_single_rewrite_resolves_runtime_context(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
        ),
    )

    context = _service(
        repository=repository,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )

    assert context.workspace_id == "workspace_test"
    assert context.operation is EnterpriseQuotaOperation.SINGLE_REWRITE
    assert context.occurred_at == NOW + timedelta(hours=1)
    assert context.window == WINDOW
    assert context.accounting_group_id == "quota_group_test"


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_multi_candidate_resolves_all_required_dimensions(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        ),
    )

    context = _service(
        repository=repository,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
    )

    assert context.window == WINDOW


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_long_document_resolves_all_required_dimensions(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
        ),
    )

    context = _service(
        repository=repository,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
    )

    assert context.window == WINDOW


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_output_characters_are_not_required_pre_execution(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        ),
    )

    context = _service(
        repository=repository,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )

    assert context.window == WINDOW


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_missing_required_active_limit_fails_closed(
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
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        )
    )

    with pytest.raises(
        EnterpriseQuotaRuntimeContextResolutionError,
        match="no active limit for dimension=input_characters",
    ):
        _service(
            repository=repository,
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_expired_required_limit_fails_closed(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    expired_window = EnterpriseQuotaWindow(
        window_start=NOW - timedelta(days=2),
        window_end=NOW - timedelta(days=1),
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        ),
        window=expired_window,
    )

    with pytest.raises(
        EnterpriseQuotaRuntimeContextResolutionError,
        match="no active limit",
    ):
        _service(
            repository=repository,
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_mismatched_active_windows_fail_closed(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    wider_window = EnterpriseQuotaWindow(
        window_start=NOW - timedelta(hours=1),
        window_end=WINDOW.window_end,
    )

    repository.create(
        _limit(
            quota_limit_id="requests",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            window=WINDOW,
        )
    )

    repository.create(
        _limit(
            quota_limit_id="input",
            dimension=EnterpriseQuotaDimension.INPUT_CHARACTERS,
            window=wider_window,
        )
    )

    with pytest.raises(
        EnterpriseQuotaRuntimeContextResolutionError,
        match="do not share one exact quota window",
    ):
        _service(
            repository=repository,
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_equivalent_timezone_windows_are_common_authority(
    backend: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    offset = timezone(timedelta(hours=-7))

    equivalent_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_start.astimezone(offset),
        window_end=WINDOW.window_end.astimezone(offset),
    )

    repository.create(
        _limit(
            quota_limit_id="requests",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            window=WINDOW,
        )
    )

    repository.create(
        _limit(
            quota_limit_id="input",
            dimension=EnterpriseQuotaDimension.INPUT_CHARACTERS,
            window=equivalent_window,
        )
    )

    context = _service(
        repository=repository,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )

    assert context.window.window_start == WINDOW.window_start
    assert context.window.window_end == WINDOW.window_end


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_adjacent_window_boundary_resolves_new_common_window(
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

    for dimension in (
        EnterpriseQuotaDimension.REWRITE_REQUESTS,
        EnterpriseQuotaDimension.INPUT_CHARACTERS,
    ):
        repository.create(
            _limit(
                quota_limit_id=f"old_{dimension.value}",
                dimension=dimension,
                window=WINDOW,
            )
        )

        repository.create(
            _limit(
                quota_limit_id=f"new_{dimension.value}",
                dimension=dimension,
                window=next_window,
            )
        )

    context = _service(
        repository=repository,
        clock=lambda: WINDOW.window_end,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )

    assert context.window == next_window
    assert context.occurred_at == WINDOW.window_end


def test_clock_is_called_once(
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        ),
    )

    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return NOW + timedelta(hours=1)

    _service(
        repository=repository,
        clock=clock,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )

    assert calls == 1


def test_accounting_group_id_factory_is_called_once(
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        ),
    )

    calls = 0

    def id_factory() -> str:
        nonlocal calls
        calls += 1
        return "quota_group_once"

    context = _service(
        repository=repository,
        accounting_group_id_factory=id_factory,
    ).resolve(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )

    assert calls == 1
    assert context.accounting_group_id == "quota_group_once"


def test_missing_limit_does_not_mint_accounting_group_id(
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    calls = 0

    def id_factory() -> str:
        nonlocal calls
        calls += 1
        return "quota_group_should_not_exist"

    with pytest.raises(
        EnterpriseQuotaRuntimeContextResolutionError,
    ):
        _service(
            repository=repository,
            accounting_group_id_factory=id_factory,
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )

    assert calls == 0


def test_empty_workspace_id_is_rejected_before_clock(
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    clock_calls = 0

    def clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    with pytest.raises(
        ValueError,
        match="workspace_id must not be empty",
    ):
        _service(
            repository=repository,
            clock=clock,
        ).resolve(
            workspace_id="",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )

    assert clock_calls == 0


def test_naive_runtime_timestamp_is_rejected(
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    with pytest.raises(
        ValueError,
        match="timestamp must be timezone-aware",
    ):
        _service(
            repository=repository,
            clock=lambda: datetime(
                2026,
                8,
                13,
                17,
                0,
            ),
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )


@pytest.mark.parametrize(
    "invalid_group_id",
    ("",),
)
def test_empty_accounting_group_id_is_rejected(
    invalid_group_id: str,
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        ),
    )

    with pytest.raises(
        ValueError,
        match="accounting_group_id must not be empty",
    ):
        _service(
            repository=repository,
            accounting_group_id_factory=lambda: invalid_group_id,
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )


def test_non_string_accounting_group_id_is_rejected(
    tmp_path: Path,
) -> None:
    repository = _repository(
        backend="memory",
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=repository,
        dimensions=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        ),
    )

    def invalid_factory() -> str:
        return 123  # type: ignore[return-value]

    with pytest.raises(
        TypeError,
        match="accounting_group_id must be a string",
    ):
        _service(
            repository=repository,
            accounting_group_id_factory=invalid_factory,
        ).resolve(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        )
