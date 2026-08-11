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

    return cast(
        str,
        user["user_id"],
    )


def _create_workspace(
    *,
    user_id: str,
    name: str,
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
    source_samples: list[dict[str, str]],
) -> str:
    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles"),
        json={
            "user_id": user_id,
            "name": "Analysis Voice",
            "source_samples": source_samples,
        },
    )

    assert response.status_code == 201

    body = cast(
        dict[str, object],
        response.json(),
    )
    profile = cast(
        dict[str, object],
        body["profile"],
    )

    return cast(
        str,
        profile["profile_id"],
    )


def test_analyze_voice_profile_over_http() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(
        user_id=user_id,
        name="Voice Workspace",
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        source_samples=[
            {
                "sample_id": "sample_1",
                "text": ("Ship the update today. Review the evidence now. Document the outcome."),
            }
        ],
    )

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{profile_id}/analyze"),
        json={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["profile"]["profile_id"] == profile_id
    assert body["evidence"]["analyzer_version"] == "voice-dna-v1"
    assert body["evidence"]["sufficiency"] == "insufficient"
    assert len(body["evidence"]["signals"]) == 8
    assert body["profile"]["style_attributes"]["sentence_length"] == "short"
    assert body["profile"]["style_attributes"]["directness"] == "direct"

    get_response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{profile_id}"),
        params={
            "user_id": user_id,
        },
    )

    assert get_response.status_code == 200

    retrieved_body = get_response.json()

    assert retrieved_body["profile"]["style_attributes"] == body["profile"]["style_attributes"]
    assert "evidence" not in retrieved_body


def test_analyze_empty_voice_profile_returns_422() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(
        user_id=user_id,
        name="Voice Workspace",
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        source_samples=[],
    )

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{profile_id}/analyze"),
        json={
            "user_id": user_id,
        },
    )

    assert response.status_code == 422
    assert "at least one non-empty" in response.json()["detail"]


def test_analyze_unknown_voice_profile_returns_404() -> None:
    user_id = _create_user(email="owner@example.com")
    workspace_id = _create_workspace(
        user_id=user_id,
        name="Voice Workspace",
    )

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/voice_missing/analyze"),
        json={
            "user_id": user_id,
        },
    )

    assert response.status_code == 404


def test_outsider_cannot_analyze_voice_profile() -> None:
    owner_id = _create_user(email="owner@example.com")
    outsider_id = _create_user(email="outsider@example.com")

    workspace_id = _create_workspace(
        user_id=owner_id,
        name="Voice Workspace",
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=owner_id,
        source_samples=[
            {
                "sample_id": "sample_1",
                "text": "Ship the update today.",
            }
        ],
    )

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{profile_id}/analyze"),
        json={
            "user_id": outsider_id,
        },
    )

    assert response.status_code == 403


def test_cross_workspace_voice_analysis_is_forbidden() -> None:
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

    profile_id = _create_profile(
        workspace_id=first_workspace_id,
        user_id=first_user_id,
        source_samples=[
            {
                "sample_id": "sample_1",
                "text": "Document the result.",
            }
        ],
    )

    response = client.post(
        (f"/api/v2/workspaces/{second_workspace_id}/voice-profiles/{profile_id}/analyze"),
        json={
            "user_id": second_user_id,
        },
    )

    assert response.status_code == 403
