from __future__ import annotations

from app.v2.domain.claim_lock import (
    ClaimLockOrigin,
)
from app.v2.services.claim_extractor import (
    ClaimExtractionDecision,
    ClaimExtractionReason,
    ClaimExtractor,
    ClaimSelectionPolicy,
)


def test_single_statement_becomes_protected_claim() -> None:
    result = ClaimExtractor().extract(text="Revenue was 42 million in 2025.")

    assert len(result.claims) == 1
    assert result.claims[0].text == "Revenue was 42 million in 2025."

    assert len(result.segments) == 1
    assert result.segments[0].decision is ClaimExtractionDecision.SELECTED
    assert result.segments[0].claim_id == result.claims[0].claim_id


def test_multiple_sentences_are_extracted_in_source_order() -> None:
    result = ClaimExtractor().extract(
        text=(
            "Revenue was 42 million. The review completed successfully. Deployment begins tomorrow."
        )
    )

    assert [claim.text for claim in result.claims] == [
        "Revenue was 42 million.",
        "The review completed successfully.",
        "Deployment begins tomorrow.",
    ]


def test_source_spans_reference_exact_source_text() -> None:
    text = "  Revenue was 42 million.   Deployment completed today.  "

    result = ClaimExtractor().extract(text=text)

    assert result.segments[0].matched_text == "Revenue was 42 million."
    assert text[result.segments[0].start : result.segments[0].end] == "Revenue was 42 million."


def test_newline_creates_statement_boundary() -> None:
    result = ClaimExtractor().extract(text=("Revenue was 42 million\nDeployment completed today"))

    assert [claim.text for claim in result.claims] == [
        "Revenue was 42 million",
        "Deployment completed today",
    ]


def test_final_unpunctuated_statement_is_extracted() -> None:
    result = ClaimExtractor().extract(text="Deployment completed successfully")

    assert len(result.claims) == 1
    assert result.claims[0].text == "Deployment completed successfully"


def test_decimal_does_not_create_false_sentence_boundary() -> None:
    result = ClaimExtractor().extract(
        text=("Revenue increased by 42.5 million. Deployment completed today.")
    )

    assert len(result.claims) == 2
    assert result.claims[0].text == "Revenue increased by 42.5 million."


def test_common_abbreviation_does_not_create_false_boundary() -> None:
    result = ClaimExtractor().extract(
        text=("Dr. Smith approved the release. Deployment starts tomorrow.")
    )

    assert len(result.claims) == 2
    assert result.claims[0].text == "Dr. Smith approved the release."


def test_dotted_initialism_does_not_create_false_boundary() -> None:
    result = ClaimExtractor().extract(
        text=("The U.S. team approved the release. Deployment starts tomorrow.")
    )

    assert len(result.claims) == 2
    assert result.claims[0].text == "The U.S. team approved the release."


def test_questions_are_excluded_by_default() -> None:
    result = ClaimExtractor().extract(
        text=("Was the release approved? The release was approved yesterday.")
    )

    assert len(result.claims) == 1
    assert result.claims[0].text == "The release was approved yesterday."

    assert result.segments[0].decision is ClaimExtractionDecision.SKIPPED
    assert result.segments[0].reason is ClaimExtractionReason.QUESTION_EXCLUDED


def test_policy_can_include_questions() -> None:
    result = ClaimExtractor().extract(
        text="Was the release approved?",
        policy=ClaimSelectionPolicy(
            include_questions=True,
        ),
    )

    assert len(result.claims) == 1
    assert result.claims[0].text == "Was the release approved?"


def test_short_fragments_are_skipped_with_evidence() -> None:
    result = ClaimExtractor().extract(text=("Approved. The release was approved yesterday."))

    assert len(result.claims) == 1

    first_segment = result.segments[0]

    assert first_segment.decision is ClaimExtractionDecision.SKIPPED
    assert first_segment.reason is ClaimExtractionReason.BELOW_MINIMUM_WORDS
    assert first_segment.claim_id is None


def test_policy_can_lower_minimum_word_count() -> None:
    result = ClaimExtractor().extract(
        text="Access denied.",
        policy=ClaimSelectionPolicy(
            minimum_word_count=2,
        ),
    )

    assert len(result.claims) == 1


def test_repeated_claim_deduplicates_object_but_preserves_segments() -> None:
    result = ClaimExtractor().extract(
        text=("Deployment completed today. Deployment completed today.")
    )

    assert len(result.claims) == 1

    selected_segments = [
        segment
        for segment in result.segments
        if (segment.decision is ClaimExtractionDecision.SELECTED)
    ]

    assert len(selected_segments) == 2
    assert selected_segments[0].claim_id == selected_segments[1].claim_id


def test_repeated_claim_deduplication_is_case_insensitive() -> None:
    result = ClaimExtractor().extract(
        text=("Deployment completed today. DEPLOYMENT completed today.")
    )

    assert len(result.claims) == 1


def test_claim_ids_are_stable_across_runs() -> None:
    extractor = ClaimExtractor()

    first = extractor.extract(text="Revenue was 42 million.")
    second = extractor.extract(text="Revenue was 42 million.")

    assert first.claims[0].claim_id == second.claims[0].claim_id


def test_claim_provenance_is_propagated() -> None:
    result = ClaimExtractor().extract(
        text="The policy requires human review.",
        origin=ClaimLockOrigin.WORKSPACE,
        source_reference="workspace-policy-9",
    )

    claim = result.claims[0]

    assert claim.provenance.origin is ClaimLockOrigin.WORKSPACE
    assert claim.provenance.source_reference == "workspace-policy-9"


def test_empty_text_produces_empty_result() -> None:
    result = ClaimExtractor().extract(text="")

    assert result.claims == ()
    assert result.segments == ()
    assert result.selected_count == 0
    assert result.skipped_count == 0


def test_segment_counts_are_explicit() -> None:
    result = ClaimExtractor().extract(text=("Approved. Deployment completed successfully."))

    assert result.selected_count == 1
    assert result.skipped_count == 1


def test_extractor_version_is_explicit() -> None:
    result = ClaimExtractor().extract(text="Deployment completed successfully.")

    assert result.extractor_version == "claim-extractor-v1"
