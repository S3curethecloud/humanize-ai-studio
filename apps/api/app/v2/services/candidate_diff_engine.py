from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.v2.domain.rewrite_candidates import (
    CandidateDiffOperation,
    CandidateDiffSegment,
    RewriteCandidate,
    RewriteCandidateDiff,
    RewriteCandidateDiffSet,
    RewriteCandidateSet,
)

CANDIDATE_DIFF_VERSION = "candidate-diff-v1"

_TOKEN_PATTERN = re.compile(
    r"\s+|\w+|[^\w\s]+",
    flags=re.UNICODE,
)


class CandidateDiffEngine:
    version = CANDIDATE_DIFF_VERSION

    def build_diff(
        self,
        *,
        source_text: str,
        candidate: RewriteCandidate,
    ) -> RewriteCandidateDiff:
        source_tokens = self._tokenize(source_text)
        candidate_tokens = self._tokenize(candidate.rewritten_text)

        matcher = SequenceMatcher(
            a=source_tokens,
            b=candidate_tokens,
            autojunk=False,
        )

        segments = tuple(
            self._segment_from_opcode(
                tag=tag,
                source_tokens=source_tokens,
                candidate_tokens=candidate_tokens,
                source_start=source_start,
                source_end=source_end,
                candidate_start=candidate_start,
                candidate_end=candidate_end,
            )
            for (
                tag,
                source_start,
                source_end,
                candidate_start,
                candidate_end,
            ) in matcher.get_opcodes()
        )

        diff = RewriteCandidateDiff(
            diff_version=self.version,
            candidate_id=candidate.candidate_id,
            segments=segments,
        )

        self._require_lossless_reconstruction(
            source_text=source_text,
            candidate_text=candidate.rewritten_text,
            diff=diff,
        )

        return diff

    def build_diff_set(
        self,
        *,
        candidate_set: RewriteCandidateSet,
    ) -> RewriteCandidateDiffSet:
        return RewriteCandidateDiffSet(
            candidate_set_id=(candidate_set.candidate_set_id),
            diffs=tuple(
                self.build_diff(
                    source_text=candidate_set.source_text,
                    candidate=candidate,
                )
                for candidate in candidate_set.candidates
            ),
        )

    @staticmethod
    def _tokenize(
        text: str,
    ) -> tuple[str, ...]:
        return tuple(match.group(0) for match in _TOKEN_PATTERN.finditer(text))

    @staticmethod
    def _segment_from_opcode(
        *,
        tag: str,
        source_tokens: tuple[str, ...],
        candidate_tokens: tuple[str, ...],
        source_start: int,
        source_end: int,
        candidate_start: int,
        candidate_end: int,
    ) -> CandidateDiffSegment:
        source_text = "".join(source_tokens[source_start:source_end])
        candidate_text = "".join(candidate_tokens[candidate_start:candidate_end])

        operation = {
            "equal": CandidateDiffOperation.EQUAL,
            "insert": CandidateDiffOperation.INSERT,
            "delete": CandidateDiffOperation.DELETE,
            "replace": CandidateDiffOperation.REPLACE,
        }.get(tag)

        if operation is None:
            raise ValueError(f"unsupported diff opcode: {tag}")

        return CandidateDiffSegment(
            operation=operation,
            source_text=source_text,
            candidate_text=candidate_text,
        )

    @staticmethod
    def _require_lossless_reconstruction(
        *,
        source_text: str,
        candidate_text: str,
        diff: RewriteCandidateDiff,
    ) -> None:
        reconstructed_source = "".join(segment.source_text for segment in diff.segments)
        reconstructed_candidate = "".join(segment.candidate_text for segment in diff.segments)

        if reconstructed_source != source_text:
            raise RuntimeError("candidate diff failed source reconstruction")

        if reconstructed_candidate != candidate_text:
            raise RuntimeError("candidate diff failed candidate reconstruction")
