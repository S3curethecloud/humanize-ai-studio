from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import V2Services

client = TestClient(app)


def setup_function() -> None:
    v2_routes.services = V2Services()


def test_create_user() -> None:
    response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["user"]["email"] == "owner@example.com"
    assert body["user"]["user_id"].startswith("user_")


def test_create_workspace_for_user() -> None:
    user_response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )
    user_id = user_response.json()["user"]["user_id"]

    response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "Example Workspace",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["workspace"]["name"] == "Example Workspace"
    assert body["workspace"]["created_by_user_id"] == user_id


def test_unknown_user_cannot_create_workspace() -> None:
    response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": "missing-user",
            "name": "Example Workspace",
        },
    )

    assert response.status_code == 404


def test_owner_can_read_empty_history() -> None:
    user_response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )
    user_id = user_response.json()["user"]["user_id"]

    workspace_response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "Example Workspace",
        },
    )
    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/history"),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["records"] == []


def test_outsider_cannot_read_workspace_history() -> None:
    owner_response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )
    owner_id = owner_response.json()["user"]["user_id"]

    outsider_response = client.post(
        "/api/v2/users",
        json={
            "email": "outsider@example.com",
            "display_name": "Outsider",
        },
    )
    outsider_id = outsider_response.json()["user"]["user_id"]

    workspace_response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": owner_id,
            "name": "Example Workspace",
        },
    )
    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/history"),
        params={
            "user_id": outsider_id,
        },
    )

    assert response.status_code == 403


def test_workspace_rewrite_is_persisted_to_history() -> None:
    user_response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )
    assert user_response.status_code == 201

    user_id = user_response.json()["user"]["user_id"]

    workspace_response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "Example Workspace",
        },
    )
    assert workspace_response.status_code == 201

    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    rewrite_response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/rewrites"),
        json={
            "user_id": user_id,
            "rewrite": {
                "text": (
                    "Furthermore, it is important to note that the team completed the migration."
                ),
                "document_type": "general",
                "audience": "general audience",
                "tone": "natural and clear",
                "intensity": "natural_rewrite",
                "preserve_numbers": True,
                "preserve_dates": True,
            },
        },
    )

    assert rewrite_response.status_code == 200

    body = rewrite_response.json()

    assert body["rewrite"]["trace_id"] == body["history"]["trace_id"]

    history_response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/history"),
        params={
            "user_id": user_id,
        },
    )

    assert history_response.status_code == 200

    records = history_response.json()["records"]

    assert len(records) == 1
    assert records[0]["trace_id"] == body["rewrite"]["trace_id"]
