from __future__ import annotations

import pytest

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    WorkflowState,
)
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.models import (
    VoiceConcision,
    VoiceContractionPreference,
    VoiceDirectness,
    VoiceFirstPersonFrequency,
    VoiceFormality,
    VoiceSentenceLength,
    VoiceSourceSample,
    VoiceStyleAttributes,
    VoiceTransitionStyle,
    VoiceWarmth,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.v2.services.voice_aware_rewrite_service import (
    VoiceAwareWorkspaceRewriteService,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


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
            primary_provider_name=(self.provider_name),
            fallback_used=False,
            provider_error_category=None,
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            ),
        )


def _settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _request() -> RewriteRequest:
    return RewriteRequest(
        text=("Revenue was 42 million in 2025. The team completed the review."),
        audience="engineering leadership",
        tone="natural and clear",
        intensity="deep_reconstruction",
        preserve_numbers=True,
        preserve_dates=True,
    )


def _build_services(
    provider: RecordingProvider,
) -> tuple[
    V2Services,
    VoiceAwareWorkspaceRewriteService,
]:
    voice_provider = VoiceAwareRewriteProvider(
        provider=provider,
    )

    workflow = RewriteWorkflow(
        provider=voice_provider,
    )

    services = V2Services(
        workflow=workflow,
        persistence_settings=_settings(),
    )

    voice_rewrite = VoiceAwareWorkspaceRewriteService(
        rewrite_service=services.rewrite,
        guidance_service=(services.voice_rewrite_guidance),
        provider=voice_provider,
    )

    return services, voice_rewrite


def _create_profile(
    services: V2Services,
) -> tuple[str, str, str]:
    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="Voice Workspace",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        name="Primary Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id="sample_1",
                text=(
                    "I keep communication clear and practical. "
                    "I explain the relevant context before the next step. "
                    "I document the outcome so the decision is easy to follow."
                ),
            ),
        ),
        style_attributes=VoiceStyleAttributes(
            formality=VoiceFormality.FORMAL,
            sentence_length=(VoiceSentenceLength.LONG),
            directness=(VoiceDirectness.DIRECT),
            warmth=VoiceWarmth.WARM,
            concision=(VoiceConcision.EXPANSIVE),
            first_person_frequency=(VoiceFirstPersonFrequency.HIGH),
            contraction_preference=(VoiceContractionPreference.PREFER),
            transition_style=(VoiceTransitionStyle.EXPLICIT),
        ),
    )

    profile = services.voice_profiles.analyze_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        profile_id=profile.profile_id,
    ).profile

    return (
        user.user_id,
        workspace.workspace_id,
        profile.profile_id,
    )


def test_provider_delegates_unchanged_without_guidance() -> None:
    recording = RecordingProvider()

    provider = VoiceAwareRewriteProvider(
        provider=recording,
    )

    request = _request()

    provider.rewrite(request)

    assert recording.requests == [request]
    assert recording.requests[0].tone == ("natural and clear")


def test_provider_injects_all_voice_dimensions_only_at_provider_boundary() -> None:
    recording = RecordingProvider()
    services, voice_rewrite = _build_services(recording)

    user_id, workspace_id, profile_id = _create_profile(services)

    original = _request()

    voice_rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
        request=original,
    )

    assert len(recording.requests) == 1

    provider_request = recording.requests[0]

    assert provider_request.text == original.text
    assert provider_request.audience == original.audience
    assert provider_request.intensity == original.intensity
    assert provider_request.preserve_numbers is original.preserve_numbers
    assert provider_request.preserve_dates is original.preserve_dates

    assert original.tone == "natural and clear"

    assert "VOICE DNA GUIDANCE" in (provider_request.tone)

    analyzed_profile = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    attributes = analyzed_profile.style_attributes

    for expected in (
        f"formality={attributes.formality.value}",
        f"sentence_length={attributes.sentence_length.value}",
        f"directness={attributes.directness.value}",
        f"warmth={attributes.warmth.value}",
        f"concision={attributes.concision.value}",
        (f"first_person_frequency={attributes.first_person_frequency.value}"),
        (f"contraction_preference={attributes.contraction_preference.value}"),
        f"transition_style={attributes.transition_style.value}",
    ):
        assert expected in provider_request.tone


def test_orchestrator_returns_guidance_with_canonical_response() -> None:
    recording = RecordingProvider()
    services, voice_rewrite = _build_services(recording)

    user_id, workspace_id, profile_id = _create_profile(services)

    result = voice_rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
        request=_request(),
    )

    assert result.guidance.profile_id == (profile_id)
    assert result.guidance.workspace_id == (workspace_id)
    assert result.guidance.guidance_version == "voice-rewrite-guidance-v1"

    assert result.history.trace_id == (result.response.trace_id)


def test_archived_profile_fails_before_provider_generation() -> None:
    recording = RecordingProvider()
    services, voice_rewrite = _build_services(recording)

    user_id, workspace_id, profile_id = _create_profile(services)

    services.voice_profiles.archive_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    with pytest.raises(
        ValueError,
        match="active voice profile",
    ):
        voice_rewrite.execute(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
            request=_request(),
        )

    assert recording.requests == []


def test_unauthorized_profile_fails_before_provider_generation() -> None:
    recording = RecordingProvider()
    services, voice_rewrite = _build_services(recording)

    _, workspace_id, profile_id = _create_profile(services)

    outsider = services.workspace.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    with pytest.raises(
        PermissionError,
        match="not a member",
    ):
        voice_rewrite.execute(
            workspace_id=workspace_id,
            user_id=outsider.user_id,
            profile_id=profile_id,
            request=_request(),
        )

    assert recording.requests == []


def test_voice_guidance_cannot_override_v1_fact_failure() -> None:
    recording = RecordingProvider(
        rewritten_text=("Revenue was 43 million in 2026. The team completed the review."),
    )

    services, voice_rewrite = _build_services(recording)

    user_id, workspace_id, profile_id = _create_profile(services)

    result = voice_rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
        request=_request(),
    )

    assert result.response.verification.decision is ReleaseDecision.FAIL

    assert WorkflowState.BLOCKED in (result.response.workflow_states)

    assert result.guidance.guardrails.voice_can_override_release_decision is False

    assert result.guidance.guardrails.v1_verification_authoritative is True
