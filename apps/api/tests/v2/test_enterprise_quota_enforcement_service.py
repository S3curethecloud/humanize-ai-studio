from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path

import pytest

from app.v2.domain.enterprise_quota import (
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
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionOutcome,
    EnterpriseQuotaDecisionService,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    EnterpriseQuotaEnforcementService,
    pre_execution_dimensions_for_operation,
)

NOW = datetime(
    2026,
    8,
    14,
    4,
    0,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=NOW,
    window_end=NOW + timedelta(days=1),
)


def _repositories(
    *,
    backend: str,
    database_path: Path,
) -> tuple[
    EnterpriseQuotaAccountingRepository,
    EnterpriseQuotaLimitRepository,
]:
    if backend == "memory":
        return (
            InMemoryEnterpriseQuotaAccountingRepository(),
            InMemoryEnterpriseQuotaLimitRepository(),
        )

    if backend == "sqlite":
        return (
            SQLiteEnterpriseQuotaAccountingRepository(
                database_path=database_path,
            ),
            SQLiteEnterpriseQuotaLimitRepository(
                database_path=database_path,
            ),
        )

    raise AssertionError(
        f"unsupported backend: {backend}"
    )


def _service(
    *,
    accounting: EnterpriseQuotaAccountingRepository,
    limits: EnterpriseQuotaLimitRepository,
) -> EnterpriseQuotaEnforcementService:
    return EnterpriseQuotaEnforcementService(
        accounting=accounting,
        limits=limits,
        decision_service=EnterpriseQuotaDecisionService(),
    )


def _create_limits(
    *,
    repository: EnterpriseQuotaLimitRepository,
    workspace_id: str,
    quantities: dict[
        EnterpriseQuotaDimension,
        int,
    ],
) -> None:
    for dimension, configured_limit in quantities.items():
        repository.create(
            EnterpriseWorkspaceQuotaLimit(
                quota_limit_id=(
                    f"limit_{workspace_id}_{dimension.value}"
                ),
                workspace_id=workspace_id,
                dimension=dimension,
                window=WINDOW,
                limit=configured_limit,
            )
        )


def _single_quantities(
    *,
    requests: int = 1,
    input_characters: int = 100,
) -> dict[
    EnterpriseQuotaDimension,
    int,
]:
    return {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: requests,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: input_characters,
    }


def _multi_quantities(
    *,
    requests: int = 1,
    input_characters: int = 100,
    candidates: int = 3,
) -> dict[
    EnterpriseQuotaDimension,
    int,
]:
    return {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: requests,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: input_characters,
        EnterpriseQuotaDimension.CANDIDATES_GENERATED: candidates,
    }


def _long_document_quantities(
    *,
    requests: int = 1,
    input_characters: int = 100,
    sections: int = 4,
) -> dict[
    EnterpriseQuotaDimension,
    int,
]:
    return {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: requests,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: input_characters,
        EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS: sections,
    }


def test_pre_execution_dimensions_exclude_output_characters() -> None:
    for operation in EnterpriseQuotaOperation:
        dimensions = pre_execution_dimensions_for_operation(
            operation
        )

        assert (
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS
            not in dimensions
        )


def test_pre_execution_dimensions_are_operation_specific() -> None:
    assert pre_execution_dimensions_for_operation(
        EnterpriseQuotaOperation.SINGLE_REWRITE
    ) == frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        }
    )

    assert pre_execution_dimensions_for_operation(
        EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE
    ) == frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        }
    )

    assert pre_execution_dimensions_for_operation(
        EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE
    ) == frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
        }
    )


@pytest.mark.parametrize(
    "backend",
    [
        "memory",
        "sqlite",
    ],
)
def test_enforce_consumes_exact_single_rewrite_group(
    *,
    backend: str,
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=limits,
        workspace_id="workspace_test",
        quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 10,
            EnterpriseQuotaDimension.INPUT_CHARACTERS: 1000,
        },
    )

    result = _service(
        accounting=accounting,
        limits=limits,
    ).enforce(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        window=WINDOW,
        accounting_group_id="group_single",
        requested_quantities=_single_quantities(),
        occurred_at=NOW,
    )

    assert result.allowed is True
    assert result.consumed is True
    assert result.workspace_id == "workspace_test"
    assert result.accounting_group_id == "group_single"
    assert all(
        decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW
        for decision in result.decisions
    )

    assert accounting.sum_usage(
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=WINDOW,
    ) == 1

    assert accounting.sum_usage(
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.INPUT_CHARACTERS,
        window=WINDOW,
    ) == 100


@pytest.mark.parametrize(
    "backend",
    [
        "memory",
        "sqlite",
    ],
)
def test_enforce_fail_closed_when_one_exact_limit_is_missing(
    *,
    backend: str,
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=limits,
        workspace_id="workspace_test",
        quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 10,
        },
    )

    result = _service(
        accounting=accounting,
        limits=limits,
    ).enforce(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        window=WINDOW,
        accounting_group_id="group_missing_limit",
        requested_quantities=_single_quantities(),
        occurred_at=NOW,
    )

    assert result.allowed is False
    assert result.consumed is False

    assert {
        decision.dimension: decision.outcome
        for decision in result.decisions
    } == {
        EnterpriseQuotaDimension.INPUT_CHARACTERS: (
            EnterpriseQuotaDecisionOutcome.NO_LIMIT_CONFIGURED
        ),
        EnterpriseQuotaDimension.REWRITE_REQUESTS: (
            EnterpriseQuotaDecisionOutcome.ALLOW
        ),
    }

    assert accounting.sum_usage(
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=WINDOW,
    ) == 0

    assert accounting.sum_usage(
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.INPUT_CHARACTERS,
        window=WINDOW,
    ) == 0


@pytest.mark.parametrize(
    "backend",
    [
        "memory",
        "sqlite",
    ],
)
def test_enforce_denial_consumes_nothing(
    *,
    backend: str,
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=limits,
        workspace_id="workspace_test",
        quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 10,
            EnterpriseQuotaDimension.INPUT_CHARACTERS: 99,
        },
    )

    result = _service(
        accounting=accounting,
        limits=limits,
    ).enforce(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        window=WINDOW,
        accounting_group_id="group_denied",
        requested_quantities=_single_quantities(
            input_characters=100,
        ),
        occurred_at=NOW,
    )

    assert result.allowed is False
    assert result.consumed is False

    assert any(
        decision.outcome
        is EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED
        for decision in result.decisions
    )

    assert accounting.sum_usage(
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=WINDOW,
    ) == 0

    assert accounting.sum_usage(
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.INPUT_CHARACTERS,
        window=WINDOW,
    ) == 0


@pytest.mark.parametrize(
    (
        "operation",
        "requested_quantities",
        "configured_limits",
    ),
    [
        (
            EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
            _multi_quantities(),
            {
                EnterpriseQuotaDimension.REWRITE_REQUESTS: 10,
                EnterpriseQuotaDimension.INPUT_CHARACTERS: 1000,
                EnterpriseQuotaDimension.CANDIDATES_GENERATED: 10,
            },
        ),
        (
            EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
            _long_document_quantities(),
            {
                EnterpriseQuotaDimension.REWRITE_REQUESTS: 10,
                EnterpriseQuotaDimension.INPUT_CHARACTERS: 1000,
                EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS: 10,
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "backend",
    [
        "memory",
        "sqlite",
    ],
)
def test_enforce_consumes_operation_specific_dimensions(
    *,
    operation: EnterpriseQuotaOperation,
    requested_quantities: dict[
        EnterpriseQuotaDimension,
        int,
    ],
    configured_limits: dict[
        EnterpriseQuotaDimension,
        int,
    ],
    backend: str,
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend=backend,
        database_path=tmp_path / "quota.db",
    )

    _create_limits(
        repository=limits,
        workspace_id="workspace_test",
        quantities=configured_limits,
    )

    result = _service(
        accounting=accounting,
        limits=limits,
    ).enforce(
        workspace_id="workspace_test",
        operation=operation,
        window=WINDOW,
        accounting_group_id=f"group_{operation.value}",
        requested_quantities=requested_quantities,
        occurred_at=NOW,
    )

    assert result.allowed is True

    assert {
        decision.dimension
        for decision in result.decisions
    } == set(
        requested_quantities
    )


def test_enforce_rejects_output_characters_pre_execution(
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend="memory",
        database_path=tmp_path / "unused.db",
    )

    quantities = _single_quantities()
    quantities[
        EnterpriseQuotaDimension.OUTPUT_CHARACTERS
    ] = 500

    service = _service(
        accounting=accounting,
        limits=limits,
    )

    with pytest.raises(
        ValueError,
        match="unexpected",
    ):
        service.enforce(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
            window=WINDOW,
            accounting_group_id="group_output",
            requested_quantities=quantities,
            occurred_at=NOW,
        )


def test_enforce_rejects_missing_required_dimension(
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend="memory",
        database_path=tmp_path / "unused.db",
    )

    service = _service(
        accounting=accounting,
        limits=limits,
    )

    with pytest.raises(
        ValueError,
        match="missing",
    ):
        service.enforce(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
            window=WINDOW,
            accounting_group_id="group_missing_quantity",
            requested_quantities={
                EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
            },
            occurred_at=NOW,
        )


def test_enforce_rejects_wrong_operation_dimension(
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend="memory",
        database_path=tmp_path / "unused.db",
    )

    service = _service(
        accounting=accounting,
        limits=limits,
    )

    with pytest.raises(
        ValueError,
        match="unexpected",
    ):
        service.enforce(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
            window=WINDOW,
            accounting_group_id="group_wrong_dimension",
            requested_quantities={
                EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
                EnterpriseQuotaDimension.INPUT_CHARACTERS: 100,
                EnterpriseQuotaDimension.CANDIDATES_GENERATED: 2,
            },
            occurred_at=NOW,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        -1,
        True,
        1.5,
    ],
)
def test_enforce_rejects_invalid_quantity(
    *,
    quantity: object,
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend="memory",
        database_path=tmp_path / "unused.db",
    )

    service = _service(
        accounting=accounting,
        limits=limits,
    )

    quantities: dict[
        EnterpriseQuotaDimension,
        object,
    ] = {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: quantity,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: 100,
    }

    expected_exception = (
        ValueError
        if isinstance(quantity, int)
        and not isinstance(quantity, bool)
        else TypeError
    )

    with pytest.raises(expected_exception):
        service.enforce(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
            window=WINDOW,
            accounting_group_id="group_invalid_quantity",
            requested_quantities=quantities,  # type: ignore[arg-type]
            occurred_at=NOW,
        )


def test_enforce_rejects_duplicate_accounting_group(
    tmp_path: Path,
) -> None:
    accounting, limits = _repositories(
        backend="memory",
        database_path=tmp_path / "unused.db",
    )

    _create_limits(
        repository=limits,
        workspace_id="workspace_test",
        quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 10,
            EnterpriseQuotaDimension.INPUT_CHARACTERS: 1000,
        },
    )

    service = _service(
        accounting=accounting,
        limits=limits,
    )

    service.enforce(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        window=WINDOW,
        accounting_group_id="group_duplicate",
        requested_quantities=_single_quantities(),
        occurred_at=NOW,
    )

    with pytest.raises(
        ValueError,
        match="group already exists",
    ):
        service.enforce(
            workspace_id="workspace_test",
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
            window=WINDOW,
            accounting_group_id="group_duplicate",
            requested_quantities=_single_quantities(),
            occurred_at=NOW,
        )
