from __future__ import annotations

from app.v2.domain.claim_lock import (
    ClaimLockOrigin,
    ProtectedValueKind,
)
from app.v2.services.claim_lock_extractor import (
    ClaimLockExtractionDetector,
    ClaimLockExtractor,
    ExplicitProtectedTerm,
)


def test_explicit_term_is_extracted_with_source_span() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="Use Humanize AI Studio for this rewrite.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Humanize AI Studio",
            ),
        ),
    )

    assert len(result.terms) == 1
    assert result.terms[0].text == "Humanize AI Studio"

    occurrences = [
        occurrence for occurrence in result.occurrences if occurrence.item_type == "term"
    ]

    assert len(occurrences) == 1
    assert occurrences[0].matched_text == "Humanize AI Studio"
    assert occurrences[0].start == 4
    assert occurrences[0].end == 22


def test_case_sensitive_explicit_term_does_not_match_different_case() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="Use humanize ai studio.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Humanize AI Studio",
                case_sensitive=True,
            ),
        ),
    )

    assert result.terms == ()


def test_case_insensitive_explicit_term_matches_source_case() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="Use humanize ai studio.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Humanize AI Studio",
                case_sensitive=False,
            ),
        ),
    )

    assert len(result.terms) == 1

    occurrence = result.occurrences[0]

    assert occurrence.matched_text == "humanize ai studio"
    assert occurrence.detector is ClaimLockExtractionDetector.EXPLICIT_TERM


def test_repeated_explicit_term_deduplicates_term_but_keeps_occurrences() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="SecureTheCloud integrates with SecureTheCloud.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="SecureTheCloud",
            ),
        ),
    )

    assert len(result.terms) == 1

    occurrences = [
        occurrence for occurrence in result.occurrences if occurrence.item_type == "term"
    ]

    assert len(occurrences) == 2
    assert occurrences[0].item_id == occurrences[1].item_id


def test_percentage_wins_over_embedded_number() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="Conversion improved by 42.5%.")

    assert len(result.values) == 1
    assert result.values[0].value == "42.5%"
    assert result.values[0].kind is ProtectedValueKind.PERCENTAGE


def test_iso_date_wins_over_component_numbers() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="The release date is 2026-08-11.")

    assert len(result.values) == 1
    assert result.values[0].value == "2026-08-11"
    assert result.values[0].kind is ProtectedValueKind.DATE


def test_month_name_date_is_extracted_as_one_value() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="The deployment completed on June 3, 2026.")

    date_values = [value for value in result.values if value.kind is ProtectedValueKind.DATE]

    assert len(date_values) == 1
    assert date_values[0].value == "June 3, 2026"


def test_slash_date_is_extracted_as_one_value() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="The review occurred on 08/11/2026.")

    assert len(result.values) == 1
    assert result.values[0].value == "08/11/2026"
    assert result.values[0].kind is ProtectedValueKind.DATE


def test_url_wins_over_values_inside_url() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text=("See https://example.com/releases/2026-08-11 for details."))

    assert len(result.values) == 1
    assert result.values[0].kind is ProtectedValueKind.URL
    assert result.values[0].value == ("https://example.com/releases/2026-08-11")


def test_url_trims_sentence_punctuation() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="Visit https://example.com/docs.")

    assert len(result.values) == 1
    assert result.values[0].value == "https://example.com/docs"


def test_hyphenated_code_is_extracted_as_code() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="Deploy build REL-2026-42 today.")

    assert len(result.values) == 1
    assert result.values[0].value == "REL-2026-42"
    assert result.values[0].kind is ProtectedValueKind.CODE


def test_mixed_alphanumeric_identifier_is_extracted() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="Request ABC12345 requires approval.")

    assert len(result.values) == 1
    assert result.values[0].value == "ABC12345"
    assert result.values[0].kind is ProtectedValueKind.IDENTIFIER


def test_plain_numbers_are_extracted() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="Revenue was $42,500.75 across 17 accounts.")

    assert [value.value for value in result.values] == [
        "$42,500.75",
        "17",
    ]

    assert all(value.kind is ProtectedValueKind.NUMBER for value in result.values)


def test_repeated_value_deduplicates_object_but_preserves_occurrences() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(text="The limit is 42 and the fallback is also 42.")

    matching_values = [value for value in result.values if value.value == "42"]

    assert len(matching_values) == 1

    value_id = matching_values[0].value_id

    occurrences = [
        occurrence for occurrence in result.occurrences if occurrence.item_id == value_id
    ]

    assert len(occurrences) == 2


def test_stable_ids_are_deterministic_across_runs() -> None:
    extractor = ClaimLockExtractor()

    first = extractor.extract(
        text="Revenue was 42 and growth was 15%.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Revenue",
            ),
        ),
    )

    second = extractor.extract(
        text="Revenue was 42 and growth was 15%.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Revenue",
            ),
        ),
    )

    assert [term.term_id for term in first.terms] == [term.term_id for term in second.terms]

    assert [value.value_id for value in first.values] == [value.value_id for value in second.values]


def test_extraction_provenance_is_propagated() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="Policy term ACME and value 42.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="ACME",
            ),
        ),
        origin=ClaimLockOrigin.WORKSPACE,
        source_reference="workspace-policy-7",
    )

    assert result.terms[0].provenance.origin is ClaimLockOrigin.WORKSPACE
    assert result.terms[0].provenance.source_reference == "workspace-policy-7"

    assert result.values[0].provenance.origin is ClaimLockOrigin.WORKSPACE
    assert result.values[0].provenance.source_reference == "workspace-policy-7"


def test_empty_text_produces_empty_extraction_result() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Humanize AI Studio",
            ),
        ),
    )

    assert result.terms == ()
    assert result.values == ()
    assert result.occurrences == ()


def test_occurrences_are_returned_in_source_order() -> None:
    extractor = ClaimLockExtractor()

    result = extractor.extract(
        text="ACME shipped 42 units on June 3, 2026.",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="ACME",
            ),
        ),
    )

    starts = [occurrence.start for occurrence in result.occurrences]

    assert starts == sorted(starts)


def test_extractor_version_is_explicit() -> None:
    result = ClaimLockExtractor().extract(text="Revenue was 42.")

    assert result.extractor_version == "claim-lock-extractor-v1"
