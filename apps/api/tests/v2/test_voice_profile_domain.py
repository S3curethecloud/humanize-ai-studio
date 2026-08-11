from app.v2.domain.models import (
    VoiceConcision,
    VoiceContractionPreference,
    VoiceDirectness,
    VoiceFirstPersonFrequency,
    VoiceFormality,
    VoiceProfileRecord,
    VoiceProfileStatus,
    VoiceSentenceLength,
    VoiceSourceSample,
    VoiceStyleAttributes,
    VoiceTransitionStyle,
    VoiceWarmth,
)
from app.v2.repositories.interfaces import (
    VoiceProfileRepository,
)


def test_voice_profile_defaults_are_safe_and_balanced() -> None:
    profile = VoiceProfileRecord(
        profile_id="voice_123",
        workspace_id="workspace_123",
        created_by_user_id="user_123",
        name="Professional Voice",
    )

    assert profile.status is VoiceProfileStatus.ACTIVE
    assert profile.source_samples == ()

    attributes = profile.style_attributes

    assert attributes.formality is VoiceFormality.BALANCED
    assert attributes.sentence_length is VoiceSentenceLength.MIXED
    assert attributes.directness is VoiceDirectness.BALANCED
    assert attributes.warmth is VoiceWarmth.BALANCED
    assert attributes.concision is VoiceConcision.BALANCED
    assert attributes.first_person_frequency is VoiceFirstPersonFrequency.MODERATE
    assert attributes.contraction_preference is VoiceContractionPreference.MIXED
    assert attributes.transition_style is VoiceTransitionStyle.NATURAL


def test_voice_profile_supports_source_samples() -> None:
    sample = VoiceSourceSample(
        sample_id="sample_123",
        text=("I prefer concise explanations with clear technical context."),
        label="interview response",
    )

    profile = VoiceProfileRecord(
        profile_id="voice_123",
        workspace_id="workspace_123",
        created_by_user_id="user_123",
        name="Interview Voice",
        source_samples=(sample,),
    )

    assert len(profile.source_samples) == 1
    assert profile.source_samples[0] == sample


def test_voice_profile_supports_explicit_style_attributes() -> None:
    attributes = VoiceStyleAttributes(
        formality=VoiceFormality.FORMAL,
        sentence_length=VoiceSentenceLength.MIXED,
        directness=VoiceDirectness.DIRECT,
        warmth=VoiceWarmth.WARM,
        concision=VoiceConcision.CONCISE,
        first_person_frequency=(VoiceFirstPersonFrequency.MODERATE),
        contraction_preference=(VoiceContractionPreference.AVOID),
        transition_style=(VoiceTransitionStyle.MINIMAL),
    )

    profile = VoiceProfileRecord(
        profile_id="voice_123",
        workspace_id="workspace_123",
        created_by_user_id="user_123",
        name="Executive Voice",
        style_attributes=attributes,
    )

    assert profile.style_attributes == attributes


def test_voice_profile_can_be_archived() -> None:
    profile = VoiceProfileRecord(
        profile_id="voice_123",
        workspace_id="workspace_123",
        created_by_user_id="user_123",
        name="Archived Voice",
        status=VoiceProfileStatus.ARCHIVED,
    )

    assert profile.status is VoiceProfileStatus.ARCHIVED


def test_voice_repository_contract_is_runtime_checkable_by_shape() -> None:
    class Repository:
        def create(
            self,
            profile: VoiceProfileRecord,
        ) -> VoiceProfileRecord:
            return profile

        def get(
            self,
            profile_id: str,
        ) -> VoiceProfileRecord | None:
            del profile_id
            return None

        def list_for_workspace(
            self,
            *,
            workspace_id: str,
            profile_status: VoiceProfileStatus | None = None,
            limit: int = 50,
        ) -> tuple[VoiceProfileRecord, ...]:
            del workspace_id
            del profile_status
            del limit
            return ()

        def update(
            self,
            profile: VoiceProfileRecord,
        ) -> VoiceProfileRecord:
            return profile

    repository: VoiceProfileRepository = Repository()

    assert repository.get("missing") is None
