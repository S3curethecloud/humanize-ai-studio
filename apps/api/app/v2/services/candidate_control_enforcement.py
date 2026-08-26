from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.candidate_generation import (
    CandidateGenerationPlan,
)
from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateGenerationExecution,
    CandidateRewriteOrchestrator,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
    ClaimLockValidator,
)


@dataclass(frozen=True)
class CandidateControlEvidence:
    candidate_id: str
    ordinal: int
    v1_release_decision: ReleaseDecision
    claim_lock_validation: ClaimLockValidationResult

    @property
    def v1_failed(self) -> bool:
        return self.v1_release_decision is ReleaseDecision.FAIL

    @property
    def claim_lock_violated(self) -> bool:
        return self.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION


@dataclass(frozen=True)
class ControlledCandidateGenerationExecution:
    generation: CandidateGenerationExecution
    claim_lock_preparation: ClaimLockPreparationResult
    effective_claim_lock: ClaimLock | None
    effective_enforcement_mode: ClaimLockEnforcementMode
    controls: tuple[
        CandidateControlEvidence,
        ...,
    ]


class CandidateClaimLockViolationError(ValueError):
    def __init__(
        self,
        *,
        controls: tuple[
            CandidateControlEvidence,
            ...,
        ],
    ) -> None:
        self.controls = controls

        self.violating_candidate_ids = tuple(
            control.candidate_id
            for control in controls
            if (not control.v1_failed and control.claim_lock_violated)
        )

        joined_ids = ", ".join(self.violating_candidate_ids)

        super().__init__(
            "candidate claim lock strict enforcement failed"
            + (f": {joined_ids}" if joined_ids else "")
        )


class ControlledCandidateRewriteOrchestrator:
    def __init__(
        self,
        *,
        candidate_orchestrator: CandidateRewriteOrchestrator,
        claim_lock_preparation_service: (ClaimLockPreparationService | None) = None,
        claim_lock_validator: (ClaimLockValidator | None) = None,
    ) -> None:
        self._candidate_orchestrator = candidate_orchestrator
        self._claim_lock_preparation_service = (
            claim_lock_preparation_service
        )
        self._claim_lock_validator = (
            claim_lock_validator or ClaimLockValidator()
        )

    def execute(
        self,
        *,
        request: RewriteRequest,
        plan: CandidateGenerationPlan,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: (
            ClaimLockEnforcementMode
        ) = ClaimLockEnforcementMode.STRICT,
        pre_resolved_claim_lock_preparation: (
            ClaimLockPreparationResult | None
        ) = None,
        effective_claim_lock: ClaimLock | None = None,
        effective_enforcement_mode: (
            ClaimLockEnforcementMode | None
        ) = None,
        pre_generation_hook: (
            Callable[[ClaimLockPreparationResult], None] | None
        ) = None,
    ) -> ControlledCandidateGenerationExecution:
        if pre_resolved_claim_lock_preparation is not None:
            if effective_enforcement_mode is None:
                raise ValueError(
                    "pre-resolved candidate Claim Lock control "
                    "requires an effective enforcement mode"
                )

            claim_lock_preparation = (
                pre_resolved_claim_lock_preparation
            )
            resolved_effective_claim_lock = (
                effective_claim_lock
            )
            resolved_effective_enforcement_mode = (
                effective_enforcement_mode
            )
        else:
            if (
                effective_claim_lock is not None
                or effective_enforcement_mode is not None
            ):
                raise ValueError(
                    "effective candidate Claim Lock control "
                    "requires pre-resolved preparation"
                )

            preparation_service = (
                self._claim_lock_preparation_service
                or ClaimLockPreparationService()
            )

            claim_lock_preparation = (
                preparation_service.prepare(
                    text=request.text,
                    explicit_terms=explicit_protected_terms,
                    enforcement_mode=(
                        claim_lock_enforcement_mode
                    ),
                )
            )

            resolved_effective_claim_lock = None
            resolved_effective_enforcement_mode = (
                claim_lock_enforcement_mode
            )

        if (
            pre_resolved_claim_lock_preparation is None
            and pre_generation_hook is not None
        ):
            pre_generation_hook(
                claim_lock_preparation
            )

        if pre_resolved_claim_lock_preparation is None:
            resolved_effective_claim_lock = (
                claim_lock_preparation.claim_lock
            )

        if (
            claim_lock_preparation.claim_lock is not None
            and resolved_effective_claim_lock is None
        ):
            raise ValueError(
                "effective candidate Claim Lock control "
                "cannot discard prepared protected items"
            )

        if (
            resolved_effective_claim_lock is not None
            and resolved_effective_claim_lock.enforcement_mode
            is not resolved_effective_enforcement_mode
        ):
            raise ValueError(
                "effective candidate Claim Lock mode "
                "does not match effective control"
            )

        if (
            pre_resolved_claim_lock_preparation is not None
            and pre_generation_hook is not None
        ):
            pre_generation_hook(
                claim_lock_preparation
            )

        generation = self._candidate_orchestrator.execute(
            request=request,
            plan=plan,
        )

        controls = self._build_controls(
            generation=generation,
            claim_lock=(
                resolved_effective_claim_lock
            ),
        )

        if (
            resolved_effective_enforcement_mode
            is ClaimLockEnforcementMode.STRICT
            and any(
                (
                    not control.v1_failed
                    and control.claim_lock_violated
                )
                for control in controls
            )
        ):
            raise CandidateClaimLockViolationError(
                controls=controls,
            )

        return ControlledCandidateGenerationExecution(
            generation=generation,
            claim_lock_preparation=(
                claim_lock_preparation
            ),
            effective_claim_lock=(
                resolved_effective_claim_lock
            ),
            effective_enforcement_mode=(
                resolved_effective_enforcement_mode
            ),
            controls=controls,
        )

    def _build_controls(
        self,
        *,
        generation: CandidateGenerationExecution,
        claim_lock: ClaimLock | None,
    ) -> tuple[
        CandidateControlEvidence,
        ...,
    ]:
        candidates = generation.candidate_set.candidates
        responses = generation.responses

        if len(candidates) != len(responses):
            raise RuntimeError(
                "candidate control enforcement requires one V1 response per candidate"
            )

        controls: list[CandidateControlEvidence] = []

        for candidate, response in zip(
            candidates,
            responses,
            strict=True,
        ):
            self._require_candidate_response_match(
                candidate_text=(candidate.rewritten_text),
                response=response,
            )

            validation = self._claim_lock_validator.validate(
                claim_lock=claim_lock,
                rewritten_text=(
                    response.rewritten_text
                ),
            )

            controls.append(
                CandidateControlEvidence(
                    candidate_id=(candidate.candidate_id),
                    ordinal=candidate.ordinal,
                    v1_release_decision=(response.verification.decision),
                    claim_lock_validation=validation,
                )
            )

        return tuple(controls)

    @staticmethod
    def _require_candidate_response_match(
        *,
        candidate_text: str,
        response: RewriteResponse,
    ) -> None:
        if candidate_text != response.rewritten_text:
            raise RuntimeError("candidate text does not match its V1 workflow response")
