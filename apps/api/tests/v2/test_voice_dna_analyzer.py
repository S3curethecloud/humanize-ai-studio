import pytest

from app.v2.domain.models import (
    VoiceConcision,
    VoiceContractionPreference,
    VoiceDirectness,
    VoiceFirstPersonFrequency,
    VoiceFormality,
    VoiceSentenceLength,
    VoiceSourceSample,
    VoiceTransitionStyle,
    VoiceWarmth,
)
from app.v2.services.voice_dna_analyzer import (
    VoiceDNAAnalyzer,
)


def _sample(
    text: str,
    *,
    sample_id: str = "sample_1",
) -> VoiceSourceSample:
    return VoiceSourceSample(
        sample_id=sample_id,
        text=text,
    )


def test_voice_dna_rejects_empty_samples() -> None:
    analyzer = VoiceDNAAnalyzer()

    with pytest.raises(
        ValueError,
        match="at least one non-empty",
    ):
        analyzer.analyze(())


def test_voice_dna_detects_short_concise_direct_voice() -> None:
    analyzer = VoiceDNAAnalyzer()

    result = analyzer.analyze(
        (_sample("Ship the change today. Review the logs now. Document the result."),)
    )

    attributes = result.style_attributes

    assert attributes.sentence_length is VoiceSentenceLength.SHORT
    assert attributes.concision is VoiceConcision.CONCISE
    assert attributes.directness is VoiceDirectness.DIRECT


def test_voice_dna_detects_first_person_and_contractions() -> None:
    analyzer = VoiceDNAAnalyzer()

    result = analyzer.analyze(
        (
            _sample(
                "I'm ready and I've reviewed it. "
                "We're aligned and we'll ship it. "
                "I think we're ready."
            ),
        )
    )

    attributes = result.style_attributes

    assert attributes.first_person_frequency is VoiceFirstPersonFrequency.HIGH
    assert attributes.contraction_preference is VoiceContractionPreference.PREFER


def test_voice_dna_detects_indirect_voice() -> None:
    analyzer = VoiceDNAAnalyzer()

    result = analyzer.analyze(
        (
            _sample(
                "Perhaps we could review this. "
                "Maybe it might need another pass. "
                "It seems the plan could change."
            ),
        )
    )

    assert result.style_attributes.directness is VoiceDirectness.INDIRECT


def test_voice_dna_detects_warm_voice() -> None:
    analyzer = VoiceDNAAnalyzer()

    result = analyzer.analyze(
        (
            _sample(
                "Thank you for the update. "
                "I appreciate the detailed review. "
                "I'm glad we completed the work."
            ),
        )
    )

    assert result.style_attributes.warmth is VoiceWarmth.WARM


def test_voice_dna_detects_explicit_transitions() -> None:
    analyzer = VoiceDNAAnalyzer()

    result = analyzer.analyze(
        (
            _sample(
                "However, the service remains stable. "
                "Therefore, deployment can continue. "
                "Finally, the team will verify it."
            ),
        )
    )

    assert result.style_attributes.transition_style is VoiceTransitionStyle.EXPLICIT


def test_voice_dna_detects_formal_voice() -> None:
    analyzer = VoiceDNAAnalyzer()

    result = analyzer.analyze(
        (
            _sample(
                "Therefore, the control requires review. "
                "Furthermore, the team must ensure compliance. "
                "Accordingly, the evidence requires validation."
            ),
        )
    )

    assert result.style_attributes.formality is VoiceFormality.FORMAL


def test_voice_dna_evidence_is_deterministic() -> None:
    analyzer = VoiceDNAAnalyzer()

    samples = (_sample("However, I appreciate the review. We will document the result."),)

    first = analyzer.analyze(samples)
    second = analyzer.analyze(samples)

    assert first == second

    assert first.evidence.analyzer_version == ("voice-dna-v1")
    assert first.evidence.sample_count == 1
    assert first.evidence.word_count > 0
    assert first.evidence.sentence_count == 2
    assert len(first.evidence.signals) == 8
