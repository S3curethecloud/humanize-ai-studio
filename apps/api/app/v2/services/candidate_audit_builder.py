from __future__ import annotations

from app.v2.domain.candidate_audit import (
    CandidateAuditSnapshot,
    CandidateClaimLockControlSnapshot,
    CandidateControlAuditSnapshot,
)
from app.v2.domain.candidate_ranking import (
    CandidateSelectionEvidence,
)
from app.v2.services.candidate_control_enforcement import (
    ControlledCandidateGenerationExecution,
)


class CandidateAuditBuildError(ValueError):
    pass


class CandidateAuditBuilder:
    def build(
        self,
        *,
        controlled_execution: (ControlledCandidateGenerationExecution),
        selection: CandidateSelectionEvidence,
    ) -> CandidateAuditSnapshot:
        candidate_set = controlled_execution.generation.candidate_set

        if selection.candidate_set_id != candidate_set.candidate_set_id:
            raise CandidateAuditBuildError(
                "candidate selection does not match controlled candidate set"
            )

        candidates = candidate_set.candidates
        controls = controlled_execution.controls

        if len(candidates) != len(controls):
            raise CandidateAuditBuildError(
                "candidate audit requires one control record per candidate"
            )

        audit_controls: list[CandidateControlAuditSnapshot] = []

        for candidate, control in zip(
            candidates,
            controls,
            strict=True,
        ):
            if candidate.candidate_id != control.candidate_id:
                raise CandidateAuditBuildError("candidate audit candidate IDs are not aligned")

            if candidate.ordinal != control.ordinal:
                raise CandidateAuditBuildError("candidate audit ordinals are not aligned")

            validation = control.claim_lock_validation

            audit_controls.append(
                CandidateControlAuditSnapshot(
                    candidate_id=(control.candidate_id),
                    ordinal=control.ordinal,
                    v1_release_decision=(control.v1_release_decision),
                    claim_lock=(
                        CandidateClaimLockControlSnapshot(
                            validator_version=(validation.validator_version),
                            lock_id=validation.lock_id,
                            enforcement_mode=(validation.enforcement_mode),
                            decision=(validation.decision),
                            violating_item_ids=(validation.violating_item_ids),
                            unevaluated_claim_ids=(validation.unevaluated_claim_ids),
                        )
                    ),
                )
            )

        return CandidateAuditSnapshot(
            candidate_set_id=(candidate_set.candidate_set_id),
            controls=tuple(audit_controls),
            selection=selection,
            selected_candidate_id=(selection.selected_candidate_id),
        )
