from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class CandidateDiffOperation(StrEnum):
    EQUAL = "equal"
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"


class RewriteCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(
        ge=1,
    )
    rewritten_text: str = Field(
        min_length=1,
        max_length=100_000,
    )


class RewriteCandidateSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_set_id: str = Field(
        min_length=1,
        max_length=200,
    )
    source_text: str = Field(
        min_length=1,
        max_length=100_000,
    )
    candidates: tuple[
        RewriteCandidate,
        ...,
    ] = Field(
        min_length=2,
        max_length=5,
    )

    @model_validator(mode="after")
    def require_candidate_integrity(
        self,
    ) -> RewriteCandidateSet:
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)

        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate IDs must be unique")

        ordinals = tuple(candidate.ordinal for candidate in self.candidates)

        expected_ordinals = tuple(
            range(
                1,
                len(self.candidates) + 1,
            )
        )

        if ordinals != expected_ordinals:
            raise ValueError("candidate ordinals must be contiguous and ordered from 1")

        rewritten_texts = tuple(candidate.rewritten_text for candidate in self.candidates)

        if len(set(rewritten_texts)) != len(rewritten_texts):
            raise ValueError("candidate rewritten texts must be unique")

        return self


class CandidateDiffSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: CandidateDiffOperation
    source_text: str = ""
    candidate_text: str = ""

    @model_validator(mode="after")
    def require_operation_shape(
        self,
    ) -> CandidateDiffSegment:
        if self.operation is CandidateDiffOperation.EQUAL:
            if not self.source_text:
                raise ValueError("equal segment requires source text")

            if self.source_text != self.candidate_text:
                raise ValueError("equal segment text must match")

        elif self.operation is CandidateDiffOperation.INSERT:
            if self.source_text:
                raise ValueError("insert segment cannot contain source text")

            if not self.candidate_text:
                raise ValueError("insert segment requires candidate text")

        elif self.operation is CandidateDiffOperation.DELETE:
            if not self.source_text:
                raise ValueError("delete segment requires source text")

            if self.candidate_text:
                raise ValueError("delete segment cannot contain candidate text")

        elif self.operation is CandidateDiffOperation.REPLACE:
            if not self.source_text or not self.candidate_text:
                raise ValueError("replace segment requires both source and candidate text")

            if self.source_text == self.candidate_text:
                raise ValueError("replace segment texts must differ")

        return self


class RewriteCandidateDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    diff_version: str = Field(
        min_length=1,
        max_length=200,
    )
    candidate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    segments: tuple[
        CandidateDiffSegment,
        ...,
    ] = Field(
        min_length=1,
    )

    @property
    def changed_segment_count(
        self,
    ) -> int:
        return sum(
            segment.operation is not CandidateDiffOperation.EQUAL for segment in self.segments
        )


class RewriteCandidateDiffSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_set_id: str = Field(
        min_length=1,
        max_length=200,
    )
    diffs: tuple[
        RewriteCandidateDiff,
        ...,
    ] = Field(
        min_length=2,
        max_length=5,
    )

    @model_validator(mode="after")
    def require_unique_candidate_diffs(
        self,
    ) -> RewriteCandidateDiffSet:
        candidate_ids = tuple(diff.candidate_id for diff in self.diffs)

        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate diff IDs must be unique")

        return self
