from pathlib import Path

import pytest

from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeService,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.factory import (
    ExternalPersistenceUnavailableError,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def test_memory_backend_builds_service_container() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="Memory Workspace",
    )

    membership = services.workspace.require_membership(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
    )

    assert membership.user_id == user.user_id


def test_sqlite_backend_survives_container_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    first = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    user = first.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = first.workspace.create_workspace(
        user_id=user.user_id,
        name="Persistent Workspace",
    )

    second = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    membership = second.workspace.require_membership(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
    )

    assert membership.workspace_id == (workspace.workspace_id)
    assert membership.user_id == user.user_id


def test_external_backend_fails_closed() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url=("postgresql://example.invalid/db"),
    )

    with pytest.raises(
        ExternalPersistenceUnavailableError,
        match="no production database adapter",
    ):
        V2Services(
            workflow=RewriteWorkflow(),
            persistence_settings=settings,
        )


def test_sqlite_workspace_creation_is_atomic(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "atomic.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="Atomic Workspace",
    )

    recreated = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    membership = recreated.workspace.require_membership(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
    )

    assert membership.workspace_id == (workspace.workspace_id)


def test_sqlite_workspace_creation_rolls_back_on_membership_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.v2.repositories.unit_of_work import (
        TransactionalMembershipRepository,
    )

    database_path = tmp_path / "rollback.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    original_create = TransactionalMembershipRepository.create

    def fail_membership_create(
        self: TransactionalMembershipRepository,
        membership: object,
    ) -> object:
        del self
        del membership
        raise RuntimeError("simulated membership failure")

    monkeypatch.setattr(
        TransactionalMembershipRepository,
        "create",
        fail_membership_create,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated membership failure",
    ):
        services.workspace.create_workspace(
            user_id=user.user_id,
            name="Rollback Workspace",
        )

    monkeypatch.setattr(
        TransactionalMembershipRepository,
        "create",
        original_create,
    )

    import sqlite3

    with sqlite3.connect(str(database_path)) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM workspaces
            WHERE name = ?
            """,
            ("Rollback Workspace",),
        ).fetchone()[0]

    assert count == 0


def test_service_container_builds_one_canonical_claim_lock_runtime() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    runtime = services.enterprise_claim_lock_runtime

    assert isinstance(
        runtime,
        EnterpriseClaimLockRuntimeService,
    )

    runtime_instances = tuple(
        value
        for value in vars(services).values()
        if isinstance(
            value,
            EnterpriseClaimLockRuntimeService,
        )
    )

    assert runtime_instances == (runtime,)

    assert (
        runtime._policies
        is services.enterprise_claim_lock_policies
    )

    assert (
        runtime._authorization_gate
        is services.workspace_authorization
    )

    assert (
        runtime._preparation_service
        is services.claim_lock_preparation
    )
