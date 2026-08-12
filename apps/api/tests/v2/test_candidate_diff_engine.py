from __future__ import annotations

from app.v2.domain.rewrite_candidates import (
    CandidateDiffOperation,
    CandidateDiffSegment,
    RewriteCandidate,
    RewriteCandidateSet,
)
from app.v2.services.candidate_diff_engine import (
    CANDIDATE_DIFF_VERSION,
    CandidateDiffEngine,
)


def _candidate(
    *,
    candidate_id: str = "candidate-1",
    ordinal: int = 1,
    rewritten_text: str,
) -> RewriteCandidate:
    return RewriteCandidate(
        candidate_id=candidate_id,
        ordinal=ordinal,
        rewritten_text=rewritten_text,
    )


def _reconstruct_source(
    diff_segments: tuple[CandidateDiffSegment, ...],
) -> str:
    return "".join(segment.source_text for segment in diff_segments)


def _reconstruct_candidate(
    diff_segments: tuple[CandidateDiffSegment, ...],
) -> str:
    return "".join(segment.candidate_text for segment in diff_segments)


def test_identical_text_produces_equal_diff() -> None:
    engine = CandidateDiffEngine()

    diff = engine.build_diff(
        source_text="Revenue remained 42%.",
        candidate=_candidate(
            rewritten_text=("Revenue remained 42%."),
        ),
    )

    assert diff.diff_version == (CANDIDATE_DIFF_VERSION)
    assert diff.changed_segment_count == 0
    assert len(diff.segments) == 1
    assert diff.segments[0].operation is CandidateDiffOperation.EQUAL


def test_word_replacement_is_detected() -> None:
    engine = CandidateDiffEngine()

    diff = engine.build_diff(
        source_text="Revenue grew quickly.",
        candidate=_candidate(
            rewritten_text=("Revenue increased quickly."),
        ),
    )

    changed = tuple(
        segment
        for segment in diff.segments
        if (segment.operation is not CandidateDiffOperation.EQUAL)
    )

    assert len(changed) == 1
    assert changed[0].operation is CandidateDiffOperation.REPLACE
    assert changed[0].source_text == "grew"
    assert changed[0].candidate_text == "increased"


def test_insert_is_detected() -> None:
    engine = CandidateDiffEngine()

    diff = engine.build_diff(
        source_text="The review finished.",
        candidate=_candidate(
            rewritten_text=("The final review finished."),
        ),
    )

    assert any(
        segment.operation is CandidateDiffOperation.INSERT and segment.candidate_text == " final"
        for segment in diff.segments
    )


def test_delete_is_detected() -> None:
    engine = CandidateDiffEngine()

    diff = engine.build_diff(
        source_text=("The final review finished."),
        candidate=_candidate(
            rewritten_text=("The review finished."),
        ),
    )

    assert any(
        segment.operation is CandidateDiffOperation.DELETE and segment.source_text == " final"
        for segment in diff.segments
    )


def test_diff_preserves_whitespace_and_punctuation() -> None:
    engine = CandidateDiffEngine()

    source_text = "Revenue: 42%.\n\nReview complete."
    candidate_text = "Revenue: 42%.\nReview is complete!"

    diff = engine.build_diff(
        source_text=source_text,
        candidate=_candidate(
            rewritten_text=candidate_text,
        ),
    )

    assert _reconstruct_source(diff.segments) == source_text
    assert _reconstruct_candidate(diff.segments) == candidate_text


def test_unicode_content_is_losslessly_diffed() -> None:
    engine = CandidateDiffEngine()

    source_text = "Résumé review — complete."
    candidate_text = "Résumé review — fully complete."

    diff = engine.build_diff(
        source_text=source_text,
        candidate=_candidate(
            rewritten_text=candidate_text,
        ),
    )

    assert _reconstruct_source(diff.segments) == source_text
    assert _reconstruct_candidate(diff.segments) == candidate_text


def test_diff_generation_is_deterministic() -> None:
    engine = CandidateDiffEngine()

    candidate = _candidate(
        rewritten_text=("Revenue increased to 42% in 2026."),
    )

    first = engine.build_diff(
        source_text=("Revenue grew to 42% in 2026."),
        candidate=candidate,
    )
    second = engine.build_diff(
        source_text=("Revenue grew to 42% in 2026."),
        candidate=candidate,
    )

    assert first == second


def test_diff_set_preserves_candidate_order() -> None:
    engine = CandidateDiffEngine()

    candidate_set = RewriteCandidateSet(
        candidate_set_id="set-1",
        source_text="The review is complete.",
        candidates=(
            _candidate(
                candidate_id="candidate-1",
                ordinal=1,
                rewritten_text=("The review is finished."),
            ),
            _candidate(
                candidate_id="candidate-2",
                ordinal=2,
                rewritten_text=("The assessment is complete."),
            ),
        ),
    )

    diff_set = engine.build_diff_set(
        candidate_set=candidate_set,
    )

    assert diff_set.candidate_set_id == "set-1"
    assert tuple(diff.candidate_id for diff in diff_set.diffs) == (
        "candidate-1",
        "candidate-2",
    )


def test_every_diff_segment_reconstructs_both_sides() -> None:
    engine = CandidateDiffEngine()

    source_text = "SecureTheCloud approved POL-AI-001 on 2026-08-11 at 42%."
    candidate_text = "On 2026-08-11, SecureTheCloud approved POL-AI-001 at exactly 42%."

    diff = engine.build_diff(
        source_text=source_text,
        candidate=_candidate(
            rewritten_text=candidate_text,
        ),
    )

    assert _reconstruct_source(diff.segments) == source_text
    assert _reconstruct_candidate(diff.segments) == candidate_text
