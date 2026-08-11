from __future__ import annotations

import re

from app.v2.domain.models import (
    VoiceAnalysisConsistency,
    VoiceAnalysisEvidence,
    VoiceAnalysisResult,
    VoiceAnalysisSignal,
    VoiceAnalysisSufficiency,
    VoiceAttributeConsistency,
    VoiceConcision,
    VoiceContractionPreference,
    VoiceDirectness,
    VoiceFirstPersonFrequency,
    VoiceFormality,
    VoiceSampleConsistencyEvidence,
    VoiceSentenceLength,
    VoiceSourceSample,
    VoiceStyleAttributes,
    VoiceTransitionStyle,
    VoiceWarmth,
)

_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")

_FIRST_PERSON_PATTERN = re.compile(
    r"\b(?:i|me|my|mine|we|us|our|ours)\b",
    re.IGNORECASE,
)

_CONTRACTION_PATTERN = re.compile(
    (
        r"\b(?:"
        r"don't|doesn't|didn't|can't|won't|"
        r"isn't|aren't|wasn't|weren't|"
        r"i'm|i've|i'll|i'd|"
        r"you're|you've|you'll|you'd|"
        r"we're|we've|we'll|we'd|"
        r"they're|they've|they'll|they'd|"
        r"it's|that's|there's|here's|let's"
        r")\b"
    ),
    re.IGNORECASE,
)

_HEDGE_PATTERN = re.compile(
    (
        r"\b(?:perhaps|maybe|possibly|might|"
        r"could|seems?|appears?)\b|"
        r"\bi think\b|"
        r"\bi believe\b|"
        r"\bin my opinion\b"
    ),
    re.IGNORECASE,
)

_WARMTH_PATTERN = re.compile(
    (
        r"\b(?:thank|thanks|appreciate|"
        r"glad|happy|please|welcome|"
        r"great|hope|grateful)\b"
    ),
    re.IGNORECASE,
)

_EXPLICIT_TRANSITION_PATTERN = re.compile(
    (
        r"\b(?:however|therefore|furthermore|"
        r"moreover|consequently|additionally|"
        r"accordingly|nevertheless|"
        r"in addition|for example|"
        r"first|second|finally)\b"
    ),
    re.IGNORECASE,
)

_FORMAL_PATTERN = re.compile(
    (
        r"\b(?:therefore|however|furthermore|"
        r"moreover|consequently|accordingly|"
        r"regarding|ensure|require|requires|"
        r"required|pursuant)\b"
    ),
    re.IGNORECASE,
)

_CASUAL_PATTERN = re.compile(
    (
        r"\b(?:hey|yeah|awesome|cool|okay|ok|"
        r"gonna|wanna)\b|"
        r"\bkind of\b|"
        r"\bsort of\b"
    ),
    re.IGNORECASE,
)


class VoiceDNAAnalyzer:
    version = "voice-dna-v1"

    def analyze(
        self,
        samples: tuple[
            VoiceSourceSample,
            ...,
        ],
    ) -> VoiceAnalysisResult:
        texts = tuple(sample.text.strip() for sample in samples if sample.text.strip())

        if not texts:
            raise ValueError("Voice analysis requires at least one non-empty source sample.")

        for text in texts:
            if not _WORD_PATTERN.findall(text):
                raise ValueError(
                    "Voice analysis requires every non-empty source sample to contain words."
                )

        combined = "\n".join(texts)

        words = _WORD_PATTERN.findall(combined)
        sentences = self._sentences(texts)

        word_count = len(words)
        sentence_count = len(sentences)

        if word_count == 0:
            raise ValueError("Voice analysis requires source samples containing words.")

        average_sentence_words = word_count / sentence_count

        contraction_count = len(_CONTRACTION_PATTERN.findall(combined))
        first_person_count = len(_FIRST_PERSON_PATTERN.findall(combined))
        hedge_count = len(_HEDGE_PATTERN.findall(combined))
        warmth_count = len(_WARMTH_PATTERN.findall(combined))
        transition_count = len(_EXPLICIT_TRANSITION_PATTERN.findall(combined))
        formal_count = len(_FORMAL_PATTERN.findall(combined))
        casual_count = len(_CASUAL_PATTERN.findall(combined))

        first_person_ratio = first_person_count / word_count
        contraction_ratio = contraction_count / sentence_count
        hedge_ratio = hedge_count / sentence_count
        warmth_ratio = warmth_count / sentence_count
        transition_ratio = transition_count / sentence_count

        sentence_length = self._sentence_length(average_sentence_words)
        concision = self._concision(average_sentence_words)
        first_person_frequency = self._first_person_frequency(first_person_ratio)
        contraction_preference = self._contraction_preference(contraction_ratio)
        directness = self._directness(hedge_ratio)
        warmth = self._warmth(warmth_ratio)
        transition_style = self._transition_style(transition_ratio)

        formality_score = formal_count - casual_count - contraction_count
        formality = self._formality(formality_score)

        attributes = VoiceStyleAttributes(
            formality=formality,
            sentence_length=sentence_length,
            directness=directness,
            warmth=warmth,
            concision=concision,
            first_person_frequency=(first_person_frequency),
            contraction_preference=(contraction_preference),
            transition_style=(transition_style),
        )

        signals = (
            VoiceAnalysisSignal(
                attribute="formality",
                inferred_value=formality.value,
                metric_name="formality_score",
                metric_value=float(formality_score),
                rationale=("Formal markers minus casual markers and contractions."),
            ),
            VoiceAnalysisSignal(
                attribute="sentence_length",
                inferred_value=(sentence_length.value),
                metric_name=("average_words_per_sentence"),
                metric_value=round(
                    average_sentence_words,
                    4,
                ),
                rationale=(
                    "Average sentence length is classified using fixed word-count thresholds."
                ),
            ),
            VoiceAnalysisSignal(
                attribute="directness",
                inferred_value=directness.value,
                metric_name=("hedges_per_sentence"),
                metric_value=round(
                    hedge_ratio,
                    4,
                ),
                rationale=(
                    "Hedging language frequency is used as a deterministic directness signal."
                ),
            ),
            VoiceAnalysisSignal(
                attribute="warmth",
                inferred_value=warmth.value,
                metric_name=("warmth_markers_per_sentence"),
                metric_value=round(
                    warmth_ratio,
                    4,
                ),
                rationale=("Courtesy and positive-affect markers are measured per sentence."),
            ),
            VoiceAnalysisSignal(
                attribute="concision",
                inferred_value=concision.value,
                metric_name=("average_words_per_sentence"),
                metric_value=round(
                    average_sentence_words,
                    4,
                ),
                rationale=("Average sentence length is used as a deterministic concision proxy."),
            ),
            VoiceAnalysisSignal(
                attribute=("first_person_frequency"),
                inferred_value=(first_person_frequency.value),
                metric_name=("first_person_terms_per_word"),
                metric_value=round(
                    first_person_ratio,
                    4,
                ),
                rationale=("First-person pronouns are measured relative to total word count."),
            ),
            VoiceAnalysisSignal(
                attribute=("contraction_preference"),
                inferred_value=(contraction_preference.value),
                metric_name=("contractions_per_sentence"),
                metric_value=round(
                    contraction_ratio,
                    4,
                ),
                rationale=("Recognized contractions are measured per sentence."),
            ),
            VoiceAnalysisSignal(
                attribute="transition_style",
                inferred_value=(transition_style.value),
                metric_name=("explicit_transitions_per_sentence"),
                metric_value=round(
                    transition_ratio,
                    4,
                ),
                rationale=("Explicit transition markers are measured per sentence."),
            ),
        )

        evidence = VoiceAnalysisEvidence(
            analyzer_version=self.version,
            sufficiency=self._sufficiency(
                sample_count=len(texts),
                word_count=word_count,
                sentence_count=sentence_count,
            ),
            sample_consistency=self._sample_consistency(
                texts,
            ),
            sample_count=len(texts),
            character_count=len(combined),
            word_count=word_count,
            sentence_count=sentence_count,
            signals=signals,
        )

        return VoiceAnalysisResult(
            style_attributes=attributes,
            evidence=evidence,
        )

    def _sample_consistency(
        self,
        texts: tuple[str, ...],
    ) -> VoiceSampleConsistencyEvidence:
        sample_attributes = tuple(self._style_attributes_for_text(text) for text in texts)

        attribute_names = (
            "formality",
            "sentence_length",
            "directness",
            "warmth",
            "concision",
            "first_person_frequency",
            "contraction_preference",
            "transition_style",
        )

        if len(sample_attributes) == 1:
            attributes = tuple(
                VoiceAttributeConsistency(
                    attribute=attribute,
                    consistent=None,
                    observed_values=(
                        getattr(
                            sample_attributes[0],
                            attribute,
                        ).value,
                    ),
                )
                for attribute in attribute_names
            )

            return VoiceSampleConsistencyEvidence(
                classification=(VoiceAnalysisConsistency.NOT_APPLICABLE),
                agreement_ratio=None,
                consistent_attribute_count=0,
                divergent_attributes=(),
                attributes=attributes,
            )

        attribute_evidence: list[VoiceAttributeConsistency] = []

        divergent_attributes: list[str] = []
        consistent_count = 0

        for attribute in attribute_names:
            observed_values = tuple(
                sorted(
                    {
                        getattr(
                            sample,
                            attribute,
                        ).value
                        for sample in sample_attributes
                    }
                )
            )

            consistent = len(observed_values) == 1

            if consistent:
                consistent_count += 1
            else:
                divergent_attributes.append(attribute)

            attribute_evidence.append(
                VoiceAttributeConsistency(
                    attribute=attribute,
                    consistent=consistent,
                    observed_values=observed_values,
                )
            )

        agreement_ratio = consistent_count / len(attribute_names)

        if agreement_ratio >= 0.75:
            classification = VoiceAnalysisConsistency.COHERENT
        elif agreement_ratio >= 0.5:
            classification = VoiceAnalysisConsistency.MIXED
        else:
            classification = VoiceAnalysisConsistency.DIVERGENT

        return VoiceSampleConsistencyEvidence(
            classification=classification,
            agreement_ratio=round(
                agreement_ratio,
                4,
            ),
            consistent_attribute_count=consistent_count,
            divergent_attributes=tuple(divergent_attributes),
            attributes=tuple(attribute_evidence),
        )

    def _style_attributes_for_text(
        self,
        text: str,
    ) -> VoiceStyleAttributes:
        words = _WORD_PATTERN.findall(text)

        sentences = self._sentences((text,))

        word_count = len(words)
        sentence_count = len(sentences)

        average_sentence_words = word_count / sentence_count

        contraction_count = len(_CONTRACTION_PATTERN.findall(text))
        first_person_count = len(_FIRST_PERSON_PATTERN.findall(text))
        hedge_count = len(_HEDGE_PATTERN.findall(text))
        warmth_count = len(_WARMTH_PATTERN.findall(text))
        transition_count = len(_EXPLICIT_TRANSITION_PATTERN.findall(text))
        formal_count = len(_FORMAL_PATTERN.findall(text))
        casual_count = len(_CASUAL_PATTERN.findall(text))

        first_person_ratio = first_person_count / word_count
        contraction_ratio = contraction_count / sentence_count
        hedge_ratio = hedge_count / sentence_count
        warmth_ratio = warmth_count / sentence_count
        transition_ratio = transition_count / sentence_count

        formality_score = formal_count - casual_count - contraction_count

        return VoiceStyleAttributes(
            formality=self._formality(formality_score),
            sentence_length=self._sentence_length(average_sentence_words),
            directness=self._directness(hedge_ratio),
            warmth=self._warmth(warmth_ratio),
            concision=self._concision(average_sentence_words),
            first_person_frequency=(self._first_person_frequency(first_person_ratio)),
            contraction_preference=(self._contraction_preference(contraction_ratio)),
            transition_style=(self._transition_style(transition_ratio)),
        )

    def _sufficiency(
        self,
        *,
        sample_count: int,
        word_count: int,
        sentence_count: int,
    ) -> VoiceAnalysisSufficiency:
        if word_count < 40 or sentence_count < 3:
            return VoiceAnalysisSufficiency.INSUFFICIENT

        if word_count < 120 or sample_count < 2 or sentence_count < 6:
            return VoiceAnalysisSufficiency.LIMITED

        return VoiceAnalysisSufficiency.STRONG

    def _sentences(
        self,
        texts: tuple[str, ...],
    ) -> tuple[str, ...]:
        sentences: list[str] = []

        for text in texts:
            parts = _SENTENCE_SPLIT_PATTERN.split(text)
            sentences.extend(part.strip() for part in parts if part.strip())

        return tuple(sentences)

    def _sentence_length(
        self,
        average_words: float,
    ) -> VoiceSentenceLength:
        if average_words <= 10:
            return VoiceSentenceLength.SHORT

        if average_words >= 20:
            return VoiceSentenceLength.LONG

        return VoiceSentenceLength.MIXED

    def _concision(
        self,
        average_words: float,
    ) -> VoiceConcision:
        if average_words <= 12:
            return VoiceConcision.CONCISE

        if average_words >= 24:
            return VoiceConcision.EXPANSIVE

        return VoiceConcision.BALANCED

    def _first_person_frequency(
        self,
        ratio: float,
    ) -> VoiceFirstPersonFrequency:
        if ratio >= 0.05:
            return VoiceFirstPersonFrequency.HIGH

        if ratio >= 0.015:
            return VoiceFirstPersonFrequency.MODERATE

        return VoiceFirstPersonFrequency.LOW

    def _contraction_preference(
        self,
        ratio: float,
    ) -> VoiceContractionPreference:
        if ratio >= 0.5:
            return VoiceContractionPreference.PREFER

        if ratio > 0:
            return VoiceContractionPreference.MIXED

        return VoiceContractionPreference.AVOID

    def _directness(
        self,
        ratio: float,
    ) -> VoiceDirectness:
        if ratio >= 0.35:
            return VoiceDirectness.INDIRECT

        if ratio > 0:
            return VoiceDirectness.BALANCED

        return VoiceDirectness.DIRECT

    def _warmth(
        self,
        ratio: float,
    ) -> VoiceWarmth:
        if ratio >= 0.35:
            return VoiceWarmth.WARM

        if ratio > 0:
            return VoiceWarmth.BALANCED

        return VoiceWarmth.RESERVED

    def _transition_style(
        self,
        ratio: float,
    ) -> VoiceTransitionStyle:
        if ratio >= 0.35:
            return VoiceTransitionStyle.EXPLICIT

        if ratio > 0:
            return VoiceTransitionStyle.NATURAL

        return VoiceTransitionStyle.MINIMAL

    def _formality(
        self,
        score: int,
    ) -> VoiceFormality:
        if score >= 2:
            return VoiceFormality.FORMAL

        if score <= -2:
            return VoiceFormality.CASUAL

        return VoiceFormality.BALANCED
