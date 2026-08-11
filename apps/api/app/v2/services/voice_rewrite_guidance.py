from __future__ import annotations

from app.v2.domain.models import (
    VoiceConcision,
    VoiceContractionPreference,
    VoiceDirectness,
    VoiceFirstPersonFrequency,
    VoiceFormality,
    VoiceProfileRecord,
    VoiceProfileStatus,
    VoiceSentenceLength,
    VoiceStyleAttributes,
    VoiceTransitionStyle,
    VoiceWarmth,
)
from app.v2.domain.voice_rewrite import (
    VoiceGuidanceInstruction,
    VoiceRewriteGuidance,
)
from app.v2.services.voice_profile_service import (
    VoiceProfileService,
)

_FORMALITY_GUIDANCE = {
    VoiceFormality.CASUAL: (
        "Use conversational diction while retaining clarity and the source meaning."
    ),
    VoiceFormality.BALANCED: (
        "Use neutral professional diction without making the text artificially formal or casual."
    ),
    VoiceFormality.FORMAL: (
        "Use polished professional diction without "
        "making claims stronger or more authoritative "
        "than the source."
    ),
}

_SENTENCE_LENGTH_GUIDANCE = {
    VoiceSentenceLength.SHORT: (
        "Prefer shorter sentences while preserving all required factual content."
    ),
    VoiceSentenceLength.MIXED: ("Use a natural mix of short and medium-length sentences."),
    VoiceSentenceLength.LONG: (
        "Allow longer developed sentences where they "
        "improve flow without combining distinct claims."
    ),
}

_DIRECTNESS_GUIDANCE = {
    VoiceDirectness.DIRECT: ("State points directly without unnecessary hedging."),
    VoiceDirectness.BALANCED: (
        "Balance direct statements with context where the source supports it."
    ),
    VoiceDirectness.INDIRECT: (
        "Use measured, less forceful phrasing without weakening or changing factual claims."
    ),
}

_WARMTH_GUIDANCE = {
    VoiceWarmth.RESERVED: ("Keep the interpersonal tone restrained and matter-of-fact."),
    VoiceWarmth.BALANCED: (
        "Use moderate warmth without adding sentiment not supported by the source."
    ),
    VoiceWarmth.WARM: (
        "Use a warm, personable tone without inventing gratitude, approval, or emotional claims."
    ),
}

_CONCISION_GUIDANCE = {
    VoiceConcision.CONCISE: ("Prefer concise phrasing while retaining every material claim."),
    VoiceConcision.BALANCED: ("Balance brevity with sufficient explanatory context."),
    VoiceConcision.EXPANSIVE: (
        "Allow fuller phrasing without introducing new facts, examples, or explanations."
    ),
}

_FIRST_PERSON_GUIDANCE = {
    VoiceFirstPersonFrequency.LOW: (
        "Minimize first-person phrasing unless the source requires it."
    ),
    VoiceFirstPersonFrequency.MODERATE: (
        "Use first-person phrasing selectively where consistent with the source."
    ),
    VoiceFirstPersonFrequency.HIGH: (
        "Favor first-person phrasing when the source already supports that perspective."
    ),
}

_CONTRACTION_GUIDANCE = {
    VoiceContractionPreference.AVOID: ("Prefer expanded forms instead of contractions."),
    VoiceContractionPreference.MIXED: ("Use contractions selectively for natural flow."),
    VoiceContractionPreference.PREFER: (
        "Prefer natural contractions where they do not change meaning or emphasis."
    ),
}

_TRANSITION_GUIDANCE = {
    VoiceTransitionStyle.MINIMAL: ("Use transitions sparingly and rely on logical sentence order."),
    VoiceTransitionStyle.NATURAL: ("Use unobtrusive transitions where they improve flow."),
    VoiceTransitionStyle.EXPLICIT: (
        "Use explicit transitions where relationships between existing ideas need clarification."
    ),
}


class VoiceProfileInactiveError(ValueError):
    pass


class VoiceRewriteGuidanceTranslator:
    version = "voice-rewrite-guidance-v1"

    def translate(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        style_attributes: VoiceStyleAttributes,
    ) -> VoiceRewriteGuidance:
        instructions = (
            self._instruction(
                attribute="formality",
                value=style_attributes.formality.value,
                instruction=_FORMALITY_GUIDANCE[style_attributes.formality],
            ),
            self._instruction(
                attribute="sentence_length",
                value=(style_attributes.sentence_length.value),
                instruction=_SENTENCE_LENGTH_GUIDANCE[style_attributes.sentence_length],
            ),
            self._instruction(
                attribute="directness",
                value=style_attributes.directness.value,
                instruction=_DIRECTNESS_GUIDANCE[style_attributes.directness],
            ),
            self._instruction(
                attribute="warmth",
                value=style_attributes.warmth.value,
                instruction=_WARMTH_GUIDANCE[style_attributes.warmth],
            ),
            self._instruction(
                attribute="concision",
                value=style_attributes.concision.value,
                instruction=_CONCISION_GUIDANCE[style_attributes.concision],
            ),
            self._instruction(
                attribute="first_person_frequency",
                value=(style_attributes.first_person_frequency.value),
                instruction=_FIRST_PERSON_GUIDANCE[style_attributes.first_person_frequency],
            ),
            self._instruction(
                attribute="contraction_preference",
                value=(style_attributes.contraction_preference.value),
                instruction=_CONTRACTION_GUIDANCE[style_attributes.contraction_preference],
            ),
            self._instruction(
                attribute="transition_style",
                value=(style_attributes.transition_style.value),
                instruction=_TRANSITION_GUIDANCE[style_attributes.transition_style],
            ),
        )

        return VoiceRewriteGuidance(
            guidance_version=self.version,
            profile_id=profile_id,
            workspace_id=workspace_id,
            style_attributes=style_attributes,
            instructions=instructions,
        )

    def _instruction(
        self,
        *,
        attribute: str,
        value: str,
        instruction: str,
    ) -> VoiceGuidanceInstruction:
        return VoiceGuidanceInstruction(
            attribute=attribute,
            value=value,
            instruction=instruction,
        )


class VoiceRewriteGuidanceService:
    def __init__(
        self,
        *,
        voice_profiles: VoiceProfileService,
        translator: (VoiceRewriteGuidanceTranslator | None) = None,
    ) -> None:
        self._voice_profiles = voice_profiles
        self._translator = (
            translator if translator is not None else VoiceRewriteGuidanceTranslator()
        )

    def build_guidance(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
    ) -> VoiceRewriteGuidance:
        profile = self._voice_profiles.get_profile(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )

        self._require_active_profile(profile)

        return self._translator.translate(
            profile_id=profile.profile_id,
            workspace_id=profile.workspace_id,
            style_attributes=profile.style_attributes,
        )

    def _require_active_profile(
        self,
        profile: VoiceProfileRecord,
    ) -> None:
        if profile.status is not VoiceProfileStatus.ACTIVE:
            raise VoiceProfileInactiveError(
                "Voice rewrite guidance requires an active voice profile."
            )
