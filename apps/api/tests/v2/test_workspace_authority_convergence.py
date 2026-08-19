from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _memory_services() -> V2Services:
    return V2Services(
        workflow=RewriteWorkflow(),
    )


def _sqlite_services(
    database_path: Path,
) -> V2Services:
    return V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=(
            V2PersistenceSettings(
                backend=PersistenceBackend.SQLITE,
                sqlite_path=database_path,
                database_url=None,
            )
        ),
    )


def _create_user_and_workspace(
    client: TestClient,
) -> tuple[str, str]:
    user_response = client.post(
        "/api/v2/users",
        json={
            "email": "authority-owner@example.com",
            "display_name": "Authority Owner",
        },
    )

    assert user_response.status_code == 201

    user_id = (
        user_response.json()["user"]["user_id"]
    )

    workspace_response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "Authority Workspace",
        },
    )

    assert workspace_response.status_code == 201

    workspace_id = (
        workspace_response
        .json()["workspace"]["workspace_id"]
    )

    return user_id, workspace_id


def test_created_workspace_resolves_in_both_authorities(
    monkeypatch,
) -> None:
    services = _memory_services()

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    client = TestClient(app)

    user_id, workspace_id = (
        _create_user_and_workspace(
            client
        )
    )

    legacy_membership = (
        services.workspace.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )
    )

    assert legacy_membership.role.value == "owner"

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/access-context"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["workspace"]["workspace_id"]
        == workspace_id
    )

    assert (
        payload["membership"]["user_id"]
        == user_id
    )

    assert (
        payload["membership"]["role"]
        == "owner"
    )

    assert (
        "workspace.read"
        in payload["permissions"]
    )

    assert (
        "analytics.read"
        in payload["permissions"]
    )


def test_created_workspace_can_query_analytics_without_manual_seed(
    monkeypatch,
) -> None:
    services = _memory_services()

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    client = TestClient(app)

    user_id, workspace_id = (
        _create_user_and_workspace(
            client
        )
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/analytics"
        ),
        params={
            "user_id": user_id,
            "period_start": (
                "2026-08-19T00:00:00+00:00"
            ),
            "period_end": (
                "2026-08-20T00:00:00+00:00"
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["workspace_id"]
        == workspace_id
    )

    assert (
        payload["analytics_version"]
        == "workspace-analytics-v1"
    )


def test_sqlite_converged_workspace_survives_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = (
        tmp_path /
        "workspace-authority.db"
    )

    first = _sqlite_services(
        database_path
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        first,
    )

    client = TestClient(app)

    user_id, workspace_id = (
        _create_user_and_workspace(
            client
        )
    )

    second = _sqlite_services(
        database_path
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        second,
    )

    legacy_membership = (
        second.workspace.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )
    )

    assert legacy_membership.role.value == "owner"

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/access-context"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["workspace"]["workspace_id"]
        == workspace_id
    )

    assert (
        payload["membership"]["role"]
        == "owner"
    )


def test_sqlite_cross_authority_transaction_rolls_back(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path /
        "workspace-authority-rollback.db"
    )

    services = _sqlite_services(
        database_path
    )

    user = services.workspace.create_user(
        email="rollback@example.com",
        display_name="Rollback Owner",
    )

    original_create = (
        services
        .workspace_authority_provisioner
        .provision
    )

    def fail_after_atomic_boundary(
        **kwargs,
    ) -> None:
        enterprise_organization = (
            kwargs["enterprise_organization"]
        )

        connection = sqlite3.connect(
            str(database_path)
        )

        try:
            connection.execute(
                """
                INSERT INTO enterprise_organizations (
                    organization_id,
                    created_at,
                    payload
                )
                VALUES (?, ?, ?)
                """,
                (
                    enterprise_organization.organization_id,
                    enterprise_organization.created_at.isoformat(),
                    enterprise_organization.model_dump_json(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

        original_create(
            **kwargs
        )

    services.workspace_authority_provisioner.provision = (
        fail_after_atomic_boundary
    )

    try:
        services.workspace_provisioning.create_workspace(
            user_id=user.user_id,
            name="Rollback Workspace",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected enterprise duplicate failure."
        )

    with sqlite3.connect(
        str(database_path)
    ) as connection:
        workspace_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM workspaces
                WHERE name = ?
                """,
                ("Rollback Workspace",),
            ).fetchone()[0]
        )

        membership_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM memberships
                WHERE user_id = ?
                """,
                (user.user_id,),
            ).fetchone()[0]
        )

    assert workspace_count == 0
    assert membership_count == 0
