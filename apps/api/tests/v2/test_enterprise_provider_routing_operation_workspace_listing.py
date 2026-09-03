from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path

import pytest

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingOperationKind,
    EnterpriseProviderRoutingOperationStatus,
    EnterpriseWorkspaceProviderRoutingOperation,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.repositories.enterprise_provider_routing_operations_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository,
)


NOW = datetime(
    2026,
    9,
    2,
    23,
    30,
    tzinfo=UTC,
)


def _operation(
    *,
    operation_id: str,
    workspace_id: str,
    created_at: datetime,
) -> EnterpriseWorkspaceProviderRoutingOperation:
    return (
        EnterpriseWorkspaceProviderRoutingOperation(
            operation_id=operation_id,
            workspace_id=workspace_id,
            user_id=(
                f"user-{workspace_id}"
            ),
            operation_kind=(
                EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
            ),
            policy_id=(
                f"policy-{workspace_id}"
            ),
            policy_revision=1,
            required_capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
            status=(
                EnterpriseProviderRoutingOperationStatus.OPEN
            ),
            created_at=created_at,
            updated_at=created_at,
            revision=1,
        )
    )


def _seed(
    repository,
) -> tuple[
    EnterpriseWorkspaceProviderRoutingOperation,
    EnterpriseWorkspaceProviderRoutingOperation,
    EnterpriseWorkspaceProviderRoutingOperation,
]:
    older = _operation(
        operation_id=(
            "enterprise_routing_operation_a_older"
        ),
        workspace_id="workspace-a",
        created_at=NOW,
    )

    newer = _operation(
        operation_id=(
            "enterprise_routing_operation_a_newer"
        ),
        workspace_id="workspace-a",
        created_at=(
            NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    foreign = _operation(
        operation_id=(
            "enterprise_routing_operation_b"
        ),
        workspace_id="workspace-b",
        created_at=(
            NOW
            + timedelta(
                seconds=2
            )
        ),
    )

    repository.create(
        older
    )
    repository.create(
        newer
    )
    repository.create(
        foreign
    )

    return (
        older,
        newer,
        foreign,
    )


def _assert_workspace_listing(
    repository,
) -> None:
    older, newer, foreign = (
        _seed(
            repository
        )
    )

    records = (
        repository.list_for_workspace(
            workspace_id="workspace-a",
            limit=1000,
        )
    )

    assert records == (
        newer,
        older,
    )

    assert foreign not in records

    assert (
        repository.list_for_workspace(
            workspace_id="workspace-a",
            limit=1,
        )
        == (
            newer,
        )
    )

    assert (
        repository.list_for_workspace(
            workspace_id="workspace-missing",
            limit=1000,
        )
        == ()
    )


def _assert_invalid_queries(
    repository,
) -> None:
    with pytest.raises(
        ValueError,
        match="workspace_id must be normalized",
    ):
        repository.list_for_workspace(
            workspace_id="",
        )

    with pytest.raises(
        ValueError,
        match="workspace_id must be normalized",
    ):
        repository.list_for_workspace(
            workspace_id=" workspace-a",
        )

    with pytest.raises(
        ValueError,
        match="list limit must be between 1 and 1000",
    ):
        repository.list_for_workspace(
            workspace_id="workspace-a",
            limit=0,
        )

    with pytest.raises(
        ValueError,
        match="list limit must be between 1 and 1000",
    ):
        repository.list_for_workspace(
            workspace_id="workspace-a",
            limit=1001,
        )


def test_in_memory_workspace_listing_is_scoped_bounded_and_deterministic() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    _assert_workspace_listing(
        repository
    )

    _assert_invalid_queries(
        repository
    )


def test_sqlite_workspace_listing_is_scoped_bounded_and_restart_durable(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path
        / "routing-operation-list.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
            database_path=database_path,
        )
    )

    older, newer, foreign = (
        _seed(
            repository
        )
    )

    restarted = (
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
            database_path=database_path,
        )
    )

    records = (
        restarted.list_for_workspace(
            workspace_id="workspace-a",
            limit=1000,
        )
    )

    assert records == (
        newer,
        older,
    )

    assert foreign not in records

    assert (
        restarted.list_for_workspace(
            workspace_id="workspace-a",
            limit=1,
        )
        == (
            newer,
        )
    )

    assert (
        restarted.list_for_workspace(
            workspace_id="workspace-missing",
            limit=1000,
        )
        == ()
    )

    _assert_invalid_queries(
        restarted
    )
