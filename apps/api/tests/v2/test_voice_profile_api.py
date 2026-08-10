from typing import cast

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import (
    V2Services,
)

client = TestClient(app)


def setup_function() -> None:
    v2_routes.services = V2Services()


def _create_user(
    *,
    email: str,
) -> str:
    response = client.post(
        "/api/v2/users",
        json={
            "email": email,
            "display_name": "User",
        },
    )

    assert response.status_code == 201

    body = cast(
        dict[str, object],
        response.json(),
    )
    user = cast(
        dict[str, object],
        body["user"],
    )

    return cast(str, user["user_id"])


def _create_workspace(
    *,
    user_id: str,
    name: str = "Voice Workspace",
) -> str:
    response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": name,
        },
    )

    assert response.status_code == 201

    body = cast(
        dict[str, object],
        response.json(),
    )
    workspace = cast(
        dict[str, object],
        body["workspace"],
    )

    return cast(
        str,
        workspace["workspace_id"],
    )


def _create_profile(
    *,
    workspace_id: str,
    user_id: str,
    name: str = "Primary Voice",
) -> dict[str, object]:
    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles"),
        json={
            "user_id": user_id,
            "name": name,
            "description": ("My professional writing voice."),
            "source_samples": [
                {
                    "sample_id": "sample_1",
                    "text": ("I write clearly and directly."),
                    "label": "professional",
                }
            ],
        },
    )

    assert response.status_code == 201

    body = cast(
        dict[str, object],
        response.json(),
    )

    return cast(
        dict[str, object],
        body["profile"],
    )


def test_create_voice_profile_over_http() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(user_id=user_id)

    profile = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert profile["workspace_id"] == workspace_id
    assert profile["created_by_user_id"] == user_id
    assert profile["name"] == "Primary Voice"
    assert profile["status"] == "active"


def test_list_voice_profiles_over_http() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(user_id=user_id)

    created = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles"),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["workspace_id"] == workspace_id
    assert len(body["profiles"]) == 1
    assert body["profiles"][0]["profile_id"] == created["profile_id"]


def test_get_voice_profile_over_http() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(user_id=user_id)

    created = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{created['profile_id']}"),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["profile"]["profile_id"] == created["profile_id"]


def test_update_voice_profile_over_http() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(user_id=user_id)

    created = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    response = client.patch(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{created['profile_id']}"),
        json={
            "user_id": user_id,
            "name": "Updated Voice",
            "description": ("Updated profile description."),
        },
    )

    assert response.status_code == 200

    profile = response.json()["profile"]

    assert profile["name"] == "Updated Voice"
    assert profile["description"] == "Updated profile description."
    assert profile["workspace_id"] == workspace_id


def test_archive_voice_profile_over_http() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(user_id=user_id)

    created = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{created['profile_id']}/archive"),
        json={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["profile"]["status"] == "archived"


def test_outsider_cannot_create_voice_profile() -> None:
    owner_id = _create_user(email="owner@example.com")
    outsider_id = _create_user(email="outsider@example.com")

    workspace_id = _create_workspace(user_id=owner_id)

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles"),
        json={
            "user_id": outsider_id,
            "name": "Forbidden Voice",
        },
    )

    assert response.status_code == 403


def test_cross_workspace_profile_access_is_forbidden() -> None:
    first_user_id = _create_user(email="one@example.com")
    second_user_id = _create_user(email="two@example.com")

    first_workspace_id = _create_workspace(
        user_id=first_user_id,
        name="Workspace One",
    )
    second_workspace_id = _create_workspace(
        user_id=second_user_id,
        name="Workspace Two",
    )

    profile = _create_profile(
        workspace_id=first_workspace_id,
        user_id=first_user_id,
    )

    response = client.get(
        (f"/api/v2/workspaces/{second_workspace_id}/voice-profiles/{profile['profile_id']}"),
        params={
            "user_id": second_user_id,
        },
    )

    assert response.status_code == 403


def test_unknown_voice_profile_returns_404() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(user_id=user_id)

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/voice_missing"),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 404
