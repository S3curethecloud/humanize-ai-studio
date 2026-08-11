from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.domain.models import RewriteRequest
from app.main import app
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)

client = TestClient(app)


class RecordingProvider:
    def __init__(
        self,
        *,
        rewritten_text: str | None = None,
    ) -> None:
        self.requests: list[RewriteRequest] = []
        self._rewritten_text = rewritten_text

    @property
    def provider_name(self) -> str:
        return "recording-provider"

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        self.requests.append(request)

        text = self._rewritten_text if self._rewritten_text is not None else request.text

        return RewriteProviderResult(
            text=text,
            changes=[],
            provider_name=self.provider_name,
            model_name="recording-model",
            prompt_version="recording-v1",
            latency_ms=0.0,
            primary_provider_name=self.provider_name,
            fallback_used=False,
            provider_error_category=None,
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            ),
        )


def _configure(
    provider: RecordingProvider,
) -> V2Services:
    voice_provider = VoiceAwareRewriteProvider(
        provider=provider,
    )

    workflow = RewriteWorkflow(
        provider=voice_provider,
    )

    services = V2Services(
        workflow=workflow,
        voice_aware_provider=voice_provider,
        persistence_settings=V2PersistenceSettings(
            backend=PersistenceBackend.MEMORY,
            sqlite_path=None,
            database_url=None,
        ),
    )

    v2_routes.services = services

    return services


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
    return cast(
        str,
        response.json()["user"]["user_id"],
    )


def _create_workspace(
    *,
    user_id: str,
) -> str:
    response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "Voice Workspace",
        },
    )

    assert response.status_code == 201
    return cast(
        str,
        response.json()["workspace"]["workspace_id"],
    )


def _create_profile(
    *,
    workspace_id: str,
    user_id: str,
) -> str:
    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles"),
        json={
            "user_id": user_id,
            "name": "Primary Voice",
            "style_attributes": {
                "formality": "formal",
                "sentence_length": "long",
                "directness": "direct",
                "warmth": "warm",
                "concision": "expansive",
                "first_person_frequency": "high",
                "contraction_preference": "prefer",
                "transition_style": "explicit",
            },
        },
    )

    assert response.status_code == 201
    return cast(
        str,
        response.json()["profile"]["profile_id"],
    )


def _rewrite_payload(
    *,
    user_id: str,
    voice_profile_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": user_id,
        "rewrite": {
            "text": ("Revenue was 42 million in 2025. The team completed the review."),
            "document_type": "general",
            "audience": "engineering leadership",
            "tone": "natural and clear",
            "intensity": "deep_reconstruction",
            "preserve_numbers": True,
            "preserve_dates": True,
        },
    }

    if voice_profile_id is not None:
        payload["voice_profile_id"] = voice_profile_id

    return payload


def test_existing_rewrite_payload_remains_backward_compatible() -> None:
    provider = RecordingProvider()
    _configure(provider)

    user_id = _create_user(
        email="owner@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200
    assert len(provider.requests) == 1

    assert provider.requests[0].tone == "natural and clear"

    assert set(response.json()) == {
        "rewrite",
        "history",
    }


def test_voice_profile_selection_applies_voice_guidance() -> None:
    provider = RecordingProvider()
    _configure(provider)

    user_id = _create_user(
        email="owner@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
            voice_profile_id=profile_id,
        ),
    )

    assert response.status_code == 200
    assert len(provider.requests) == 1

    provider_request = provider.requests[0]

    assert "VOICE DNA GUIDANCE" in (provider_request.tone)
    assert "formality=formal" in (provider_request.tone)
    assert "transition_style=explicit" in (provider_request.tone)

    assert set(response.json()) == {
        "rewrite",
        "history",
        "voice",
    }

    voice = response.json()["voice"]

    assert voice == {
        "applied": True,
        "profile_id": profile_id,
        "guidance_version": ("voice-rewrite-guidance-v1"),
    }


def test_unknown_voice_profile_returns_404_before_generation() -> None:
    provider = RecordingProvider()
    _configure(provider)

    user_id = _create_user(
        email="owner@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
            voice_profile_id="voice_missing",
        ),
    )

    assert response.status_code == 404
    assert provider.requests == []


def test_archived_voice_profile_returns_409_before_generation() -> None:
    provider = RecordingProvider()
    _configure(provider)

    user_id = _create_user(
        email="owner@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    archive_response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles/{profile_id}/archive"),
        json={
            "user_id": user_id,
        },
    )

    assert archive_response.status_code == 200

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
            voice_profile_id=profile_id,
        ),
    )

    assert response.status_code == 409
    assert provider.requests == []


def test_unauthorized_voice_profile_returns_403_before_generation() -> None:
    provider = RecordingProvider()
    _configure(provider)

    owner_id = _create_user(
        email="owner@example.com",
    )
    outsider_id = _create_user(
        email="outsider@example.com",
    )

    workspace_id = _create_workspace(
        user_id=owner_id,
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=owner_id,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=outsider_id,
            voice_profile_id=profile_id,
        ),
    )

    assert response.status_code == 403
    assert provider.requests == []


def test_voice_api_cannot_override_v1_fact_failure() -> None:
    provider = RecordingProvider(
        rewritten_text=("Revenue was 43 million in 2026. The team completed the review."),
    )
    _configure(provider)

    user_id = _create_user(
        email="owner@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )
    profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
            voice_profile_id=profile_id,
        ),
    )

    assert response.status_code == 200

    rewrite = response.json()["rewrite"]

    assert rewrite["verification"]["decision"] == "fail"
    assert "blocked" in rewrite["workflow_states"]

    assert len(provider.requests) == 1


def test_non_voice_rewrite_omits_voice_evidence() -> None:
    provider = RecordingProvider()
    _configure(provider)

    user_id = _create_user(
        email="no-voice-evidence@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200
    assert "voice" not in response.json()


def test_voice_evidence_matches_selected_profile() -> None:
    provider = RecordingProvider()
    _configure(provider)

    user_id = _create_user(
        email="voice-evidence@example.com",
    )
    workspace_id = _create_workspace(
        user_id=user_id,
    )

    first_profile_id = _create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    second_response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/voice-profiles"),
        json={
            "user_id": user_id,
            "name": "Second Voice",
        },
    )

    assert second_response.status_code == 201

    second_profile_id = cast(
        str,
        second_response.json()["profile"]["profile_id"],
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
            voice_profile_id=second_profile_id,
        ),
    )

    assert response.status_code == 200

    voice = response.json()["voice"]

    assert voice["applied"] is True
    assert voice["profile_id"] == second_profile_id
    assert voice["profile_id"] != first_profile_id
    assert voice["guidance_version"] == "voice-rewrite-guidance-v1"
