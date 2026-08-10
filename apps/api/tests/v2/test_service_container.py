from pathlib import Path

import pytest

from app.v2.api.dependencies import (
    V2Services,
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
