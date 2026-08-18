from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.models import ReleaseDecision
from app.v2.domain.candidate_ranking import (
    CandidateSelectionEvidence,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)

CANDIDATE_AUDIT_VERSION: Literal["candidate-audit-v1"] = "candidate-audit-v1"


class CandidateClaimLockControlSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    validator_version: str = Field(
        min_length=1,
        max_length=200,
    )
    lock_id: str | None = Field(
        default=None,
        max_length=200,
    )
    enforcement_mode: ClaimLockEnforcementMode | None = None
    decision: ClaimLockValidationDecision

    violating_item_ids: tuple[str, ...] = ()
    unevaluated_claim_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_claim_lock_shape(
        self,
    ) -> CandidateClaimLockControlSnapshot:
        lock_fields = (
            self.lock_id,
            self.enforcement_mode,
        )
        present = tuple(value is not None for value in lock_fields)

        if any(present) and not all(present):
            raise ValueError(
                "candidate claim lock audit fields must be both present or both absent"
            )

        if self.lock_id is None and (
            self.decision is not ClaimLockValidationDecision.PASS
            or self.violating_item_ids
            or self.unevaluated_claim_ids
        ):
            raise ValueError("candidate claim lock evidence without a lock must be an empty pass")

        if self.decision is ClaimLockValidationDecision.PASS and self.violating_item_ids:
            raise ValueError("claim lock pass cannot contain violating item IDs")

        if self.decision is ClaimLockValidationDecision.VIOLATION and not self.violating_item_ids:
            raise ValueError("claim lock violation requires violating item IDs")

        return self


class CandidateControlAuditSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(ge=1)

    v1_release_decision: ReleaseDecision
    claim_lock: CandidateClaimLockControlSnapshot


class CandidateAuditSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_version: Literal["candidate-audit-v1"] = CANDIDATE_AUDIT_VERSION

    candidate_set_id: str = Field(
        min_length=1,
        max_length=200,
    )

    controls: tuple[
        CandidateControlAuditSnapshot,
        ...,
    ] = Field(
        min_length=2,
        max_length=5,
    )

    selection: CandidateSelectionEvidence

    selected_candidate_id: str | None = Field(
        default=None,
        max_length=200,
    )

    @model_validator(mode="after")
    def require_candidate_audit_integrity(
        self,
    ) -> CandidateAuditSnapshot:
        control_ids = tuple(control.candidate_id for control in self.controls)

        if len(set(control_ids)) != len(control_ids):
            raise ValueError("candidate audit control IDs must be unique")

        ordinals = tuple(control.ordinal for control in self.controls)

        if ordinals != tuple(
            range(
                1,
                len(self.controls) + 1,
            )
        ):
            raise ValueError(
                "candidate audit control ordinals must be contiguous and ordered from 1"
            )

        if self.selection.candidate_set_id != self.candidate_set_id:
            raise ValueError("candidate selection set ID must match candidate audit set ID")

        ranking_ids = {result.candidate_id for result in self.selection.ranked_candidates}

        if ranking_ids != set(control_ids):
            raise ValueError(
                "candidate audit controls must match candidate selection candidate IDs"
            )

        if self.selected_candidate_id != self.selection.selected_candidate_id:
            raise ValueError("selected candidate linkage must match selection evidence")

        return self
