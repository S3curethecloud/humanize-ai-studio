from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.domain.rewrite_candidates import (
    CandidateDiffOperation,
    CandidateDiffSegment,
    RewriteCandidate,
    RewriteCandidateDiff,
    RewriteCandidateDiffSet,
    RewriteCandidateSet,
)


def _candidate(
    *,
    candidate_id: str,
    ordinal: int,
    rewritten_text: str,
) -> RewriteCandidate:
    return RewriteCandidate(
        candidate_id=candidate_id,
        ordinal=ordinal,
        rewritten_text=rewritten_text,
    )


def test_candidate_set_requires_multiple_candidates() -> None:
    with pytest.raises(ValidationError):
        RewriteCandidateSet(
            candidate_set_id="set-1",
            source_text="Original text.",
            candidates=(
                _candidate(
                    candidate_id="candidate-1",
                    ordinal=1,
                    rewritten_text="Candidate one.",
                ),
            ),
        )


def test_candidate_set_accepts_ordered_unique_candidates() -> None:
    candidate_set = RewriteCandidateSet(
        candidate_set_id="set-1",
        source_text="Original text.",
        candidates=(
            _candidate(
                candidate_id="candidate-1",
                ordinal=1,
                rewritten_text="Candidate one.",
            ),
            _candidate(
                candidate_id="candidate-2",
                ordinal=2,
                rewritten_text="Candidate two.",
            ),
        ),
    )

    assert tuple(candidate.candidate_id for candidate in candidate_set.candidates) == (
        "candidate-1",
        "candidate-2",
    )


def test_candidate_set_rejects_duplicate_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="candidate IDs must be unique",
    ):
        RewriteCandidateSet(
            candidate_set_id="set-1",
            source_text="Original text.",
            candidates=(
                _candidate(
                    candidate_id="candidate-1",
                    ordinal=1,
                    rewritten_text="Candidate one.",
                ),
                _candidate(
                    candidate_id="candidate-1",
                    ordinal=2,
                    rewritten_text="Candidate two.",
                ),
            ),
        )


def test_candidate_set_rejects_noncontiguous_ordinals() -> None:
    with pytest.raises(
        ValidationError,
        match=("candidate ordinals must be contiguous"),
    ):
        RewriteCandidateSet(
            candidate_set_id="set-1",
            source_text="Original text.",
            candidates=(
                _candidate(
                    candidate_id="candidate-1",
                    ordinal=1,
                    rewritten_text="Candidate one.",
                ),
                _candidate(
                    candidate_id="candidate-2",
                    ordinal=3,
                    rewritten_text="Candidate two.",
                ),
            ),
        )


def test_candidate_set_rejects_duplicate_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match=("candidate rewritten texts must be unique"),
    ):
        RewriteCandidateSet(
            candidate_set_id="set-1",
            source_text="Original text.",
            candidates=(
                _candidate(
                    candidate_id="candidate-1",
                    ordinal=1,
                    rewritten_text="Same output.",
                ),
                _candidate(
                    candidate_id="candidate-2",
                    ordinal=2,
                    rewritten_text="Same output.",
                ),
            ),
        )


@pytest.mark.parametrize(
    (
        "operation",
        "source_text",
        "candidate_text",
    ),
    (
        (
            CandidateDiffOperation.EQUAL,
            "unchanged",
            "unchanged",
        ),
        (
            CandidateDiffOperation.INSERT,
            "",
            "added",
        ),
        (
            CandidateDiffOperation.DELETE,
            "removed",
            "",
        ),
        (
            CandidateDiffOperation.REPLACE,
            "before",
            "after",
        ),
    ),
)
def test_valid_diff_segment_shapes(
    operation: CandidateDiffOperation,
    source_text: str,
    candidate_text: str,
) -> None:
    segment = CandidateDiffSegment(
        operation=operation,
        source_text=source_text,
        candidate_text=candidate_text,
    )

    assert segment.operation is operation


@pytest.mark.parametrize(
    (
        "operation",
        "source_text",
        "candidate_text",
    ),
    (
        (
            CandidateDiffOperation.EQUAL,
            "before",
            "after",
        ),
        (
            CandidateDiffOperation.INSERT,
            "unexpected",
            "added",
        ),
        (
            CandidateDiffOperation.DELETE,
            "removed",
            "unexpected",
        ),
        (
            CandidateDiffOperation.REPLACE,
            "same",
            "same",
        ),
    ),
)
def test_invalid_diff_segment_shapes_are_rejected(
    operation: CandidateDiffOperation,
    source_text: str,
    candidate_text: str,
) -> None:
    with pytest.raises(ValidationError):
        CandidateDiffSegment(
            operation=operation,
            source_text=source_text,
            candidate_text=candidate_text,
        )


def test_candidate_diff_counts_changed_segments() -> None:
    diff = RewriteCandidateDiff(
        diff_version="candidate-diff-v1",
        candidate_id="candidate-1",
        segments=(
            CandidateDiffSegment(
                operation=(CandidateDiffOperation.EQUAL),
                source_text="Revenue ",
                candidate_text="Revenue ",
            ),
            CandidateDiffSegment(
                operation=(CandidateDiffOperation.REPLACE),
                source_text="grew",
                candidate_text="increased",
            ),
        ),
    )

    assert diff.changed_segment_count == 1


def test_diff_set_rejects_duplicate_candidate_ids() -> None:
    diff = RewriteCandidateDiff(
        diff_version="candidate-diff-v1",
        candidate_id="candidate-1",
        segments=(
            CandidateDiffSegment(
                operation=(CandidateDiffOperation.EQUAL),
                source_text="same",
                candidate_text="same",
            ),
        ),
    )

    with pytest.raises(
        ValidationError,
        match="candidate diff IDs must be unique",
    ):
        RewriteCandidateDiffSet(
            candidate_set_id="set-1",
            diffs=(
                diff,
                diff,
            ),
        )
