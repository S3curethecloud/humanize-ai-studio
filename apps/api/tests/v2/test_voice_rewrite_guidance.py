from datetime import UTC, datetime

import pytest

from app.domain.models import (
    ReleaseDecision,
)
from app.services.fact_extractor import (
    FactExtractor,
)
from app.services.verifier import (
    RewriteVerifier,
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
    VoiceRewriteAnalysisSnapshot,
    VoiceSentenceLength,
    VoiceSourceSample,
    VoiceStyleAttributes,
    VoiceTransitionStyle,
    VoiceWarmth,
)
from app.v2.domain.voice_rewrite import (
    VoiceConstraintPriority,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceProfileAnalysisRequiredError,
    VoiceRewriteGuidanceTranslator,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _analysis_snapshot() -> VoiceRewriteAnalysisSnapshot:
    return VoiceRewriteAnalysisSnapshot(
        analysis_state="current",
        analyzer_version="voice-dna-v1",
        analyzed_at=datetime(
            2026,
            8,
            11,
            12,
            0,
            tzinfo=UTC,
        ),
        source_sample_ids=("sample_1",),
        source_fingerprint="a" * 64,
        sample_count=1,
        sufficiency="limited",
        consistency="not_applicable",
        style_attributes=VoiceStyleAttributes(),
    )


def _services() -> V2Services:
    return V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=V2PersistenceSettings(
            backend=PersistenceBackend.MEMORY,
            sqlite_path=None,
            database_url=None,
        ),
    )


def _create_profile(
    services: V2Services,
    *,
    email: str = "owner@example.com",
    analyzed: bool = True,
) -> tuple[str, str, str]:
    user = services.workspace.create_user(
        email=email,
        display_name="Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
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
                    "I keep the message direct and practical. "
                    "I explain the important context clearly. "
                    "I document the outcome so the next step is obvious."
                ),
            ),
        ),
        style_attributes=VoiceStyleAttributes(
            formality=VoiceFormality.FORMAL,
            sentence_length=(VoiceSentenceLength.LONG),
            directness=VoiceDirectness.DIRECT,
            warmth=VoiceWarmth.WARM,
            concision=VoiceConcision.EXPANSIVE,
            first_person_frequency=(VoiceFirstPersonFrequency.HIGH),
            contraction_preference=(VoiceContractionPreference.PREFER),
            transition_style=(VoiceTransitionStyle.EXPLICIT),
        ),
    )

    if analyzed:
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


def test_translator_emits_all_eight_voice_dimensions() -> None:
    translator = VoiceRewriteGuidanceTranslator()

    attributes = VoiceStyleAttributes(
        formality=VoiceFormality.FORMAL,
        sentence_length=VoiceSentenceLength.LONG,
        directness=VoiceDirectness.DIRECT,
        warmth=VoiceWarmth.WARM,
        concision=VoiceConcision.EXPANSIVE,
        first_person_frequency=(VoiceFirstPersonFrequency.HIGH),
        contraction_preference=(VoiceContractionPreference.PREFER),
        transition_style=(VoiceTransitionStyle.EXPLICIT),
    )

    result = translator.translate(
        profile_id="voice_1",
        workspace_id="workspace_1",
        style_attributes=attributes,
        analysis_snapshot=_analysis_snapshot(),
    )

    assert result.guidance_version == ("voice-rewrite-guidance-v1")
    assert len(result.instructions) == 8

    assert {item.attribute for item in result.instructions} == {
        "formality",
        "sentence_length",
        "directness",
        "warmth",
        "concision",
        "first_person_frequency",
        "contraction_preference",
        "transition_style",
    }


def test_guidance_translation_is_deterministic() -> None:
    translator = VoiceRewriteGuidanceTranslator()
    attributes = VoiceStyleAttributes()

    first = translator.translate(
        profile_id="voice_1",
        workspace_id="workspace_1",
        style_attributes=attributes,
        analysis_snapshot=_analysis_snapshot(),
    )
    second = translator.translate(
        profile_id="voice_1",
        workspace_id="workspace_1",
        style_attributes=attributes,
        analysis_snapshot=_analysis_snapshot(),
    )

    assert first == second


def test_voice_guardrail_authority_order_is_fixed() -> None:
    translator = VoiceRewriteGuidanceTranslator()

    result = translator.translate(
        profile_id="voice_1",
        workspace_id="workspace_1",
        style_attributes=VoiceStyleAttributes(),
        analysis_snapshot=_analysis_snapshot(),
    )

    guardrails = result.guardrails

    assert guardrails.authority_order == (
        VoiceConstraintPriority.FACTUAL_PRESERVATION,
        VoiceConstraintPriority.REWRITE_REQUEST_CONSTRAINTS,
        VoiceConstraintPriority.V1_VERIFICATION,
        VoiceConstraintPriority.VOICE_MATCHING,
    )

    assert guardrails.factual_preservation_required is True
    assert guardrails.rewrite_request_constraints_authoritative is True
    assert guardrails.v1_verification_authoritative is True
    assert guardrails.voice_can_add_claims is False
    assert guardrails.voice_can_remove_claims is False
    assert guardrails.voice_can_override_release_decision is False


def test_guidance_requires_active_voice_profile() -> None:
    services = _services()

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
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )


def test_guidance_selection_preserves_workspace_authorization() -> None:
    services = _services()

    owner_id, workspace_id, profile_id = _create_profile(services)

    outsider = services.workspace.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=outsider.user_id,
            profile_id=profile_id,
        )

    guidance = services.voice_rewrite_guidance.build_guidance(
        workspace_id=workspace_id,
        user_id=owner_id,
        profile_id=profile_id,
    )

    assert guidance.profile_id == profile_id
    assert guidance.workspace_id == workspace_id


def test_v1_fact_verification_remains_authoritative() -> None:
    services = _services()

    user_id, workspace_id, profile_id = _create_profile(services)

    guidance = services.voice_rewrite_guidance.build_guidance(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    source = "Revenue was 42 million in 2025."
    voice_matched_but_invalid_candidate = "Revenue was 43 million in 2026."

    protected_facts = FactExtractor().extract(
        source,
        preserve_numbers=True,
        preserve_dates=True,
    )

    verification = RewriteVerifier().verify(
        source_text=source,
        rewritten_text=(voice_matched_but_invalid_candidate),
        protected_facts=protected_facts,
    )

    assert verification.decision is ReleaseDecision.FAIL
    assert verification.missing_facts

    assert guidance.guardrails.v1_verification_authoritative is True
    assert guidance.guardrails.voice_can_override_release_decision is False


def test_guidance_rejects_never_analyzed_voice_profile() -> None:
    services = _services()

    user_id, workspace_id, profile_id = _create_profile(
        services,
        analyzed=False,
    )

    with pytest.raises(
        VoiceProfileAnalysisRequiredError,
        match="Analyze the voice profile before using it for rewrites",
    ):
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )


def test_guidance_rejects_stale_voice_profile() -> None:
    services = _services()

    user_id, workspace_id, profile_id = _create_profile(services)

    analyzed = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    stale = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=analyzed.model_copy(
            update={
                "source_samples": (
                    VoiceSourceSample(
                        sample_id="sample_1",
                        text=("This sample changed after the prior Voice DNA analysis."),
                    ),
                ),
            }
        ),
    )

    assert stale.analysis_state.value == "stale"

    with pytest.raises(
        VoiceProfileAnalysisRequiredError,
        match="Re-analyze the voice profile before using it for rewrites",
    ):
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )
