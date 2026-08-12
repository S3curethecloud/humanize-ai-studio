from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.candidate_audit import (
    CandidateAuditSnapshot,
)
from app.v2.domain.candidate_generation import (
    CandidateGenerationPlan,
)
from app.v2.domain.candidate_ranking import (
    CandidateSelectionDecision,
    CandidateSelectionEvidence,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.claim_lock_audit import (
    ClaimLockValidationAuditSnapshot,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.domain.rewrite_candidates import (
    RewriteCandidateDiffSet,
    RewriteCandidateSet,
)
from app.v2.domain.voice_rewrite import (
    VoiceRewriteGuidance,
)
from app.v2.services.candidate_audit_builder import (
    CandidateAuditBuilder,
)
from app.v2.services.candidate_control_enforcement import (
    CandidateControlEvidence,
    ControlledCandidateGenerationExecution,
    ControlledCandidateRewriteOrchestrator,
)
from app.v2.services.candidate_diff_engine import (
    CandidateDiffEngine,
)
from app.v2.services.candidate_generation_planner import (
    CandidateGenerationPlanner,
)
from app.v2.services.candidate_ranker import (
    CandidateRanker,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateRewriteOrchestrator,
    RewriteWorkflowExecutor,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationResult,
    ClaimLockValidator,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceRewriteGuidanceService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


class NoEligibleCandidateError(ValueError):
    pass


class MultiCandidateVoiceUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class MultiCandidateWorkspaceRewriteResult:
    selected_response: RewriteResponse
    history: RewriteHistoryRecord

    candidate_set: RewriteCandidateSet
    diff_set: RewriteCandidateDiffSet
    controls: tuple[
        CandidateControlEvidence,
        ...,
    ]
    selection: CandidateSelectionEvidence
    audit_snapshot: CandidateAuditSnapshot

    claim_lock_preparation: ClaimLockPreparationResult
    selected_claim_lock_validation: ClaimLockValidationResult

    voice_guidance: VoiceRewriteGuidance | None = None


class MultiCandidateWorkspaceRewriteService:
    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        history_service: RewriteHistoryService,
        workflow: RewriteWorkflowExecutor,
        voice_guidance_service: (VoiceRewriteGuidanceService | None) = None,
        voice_provider: VoiceAwareRewriteProvider | None = None,
        planner: CandidateGenerationPlanner | None = None,
        diff_engine: CandidateDiffEngine | None = None,
        claim_lock_preparation_service: (ClaimLockPreparationService | None) = None,
        claim_lock_validator: ClaimLockValidator | None = None,
        ranker: CandidateRanker | None = None,
        audit_builder: CandidateAuditBuilder | None = None,
    ) -> None:
        self._workspace_service = workspace_service
        self._history_service = history_service
        self._voice_guidance_service = voice_guidance_service
        self._voice_provider = voice_provider

        self._planner = planner or CandidateGenerationPlanner()
        self._diff_engine = diff_engine or CandidateDiffEngine()
        self._ranker = ranker or CandidateRanker()
        self._audit_builder = audit_builder or CandidateAuditBuilder()

        candidate_orchestrator = CandidateRewriteOrchestrator(
            workflow=workflow,
        )

        self._controlled_orchestrator = ControlledCandidateRewriteOrchestrator(
            candidate_orchestrator=candidate_orchestrator,
            claim_lock_preparation_service=(
                claim_lock_preparation_service or ClaimLockPreparationService()
            ),
            claim_lock_validator=(claim_lock_validator or ClaimLockValidator()),
        )

    def execute(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        candidate_count: int,
        voice_profile_id: str | None = None,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: (ClaimLockEnforcementMode) = ClaimLockEnforcementMode.STRICT,
    ) -> MultiCandidateWorkspaceRewriteResult:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        plan = self._planner.plan(
            request=request,
            candidate_count=candidate_count,
        )

        voice_guidance = self._build_voice_guidance(
            workspace_id=workspace_id,
            user_id=user_id,
            voice_profile_id=voice_profile_id,
        )

        controlled = self._execute_controlled(
            request=request,
            plan=plan,
            voice_guidance=voice_guidance,
            explicit_protected_terms=(explicit_protected_terms),
            claim_lock_enforcement_mode=(claim_lock_enforcement_mode),
        )

        diff_set = self._diff_engine.build_diff_set(
            candidate_set=(controlled.generation.candidate_set),
        )

        selection = self._ranker.select(
            controlled_execution=controlled,
            diff_set=diff_set,
        )

        if (
            selection.decision is CandidateSelectionDecision.NONE_ELIGIBLE
            or selection.selected_candidate_id is None
        ):
            raise NoEligibleCandidateError("multi-candidate rewrite produced no eligible candidate")

        audit_snapshot = self._audit_builder.build(
            controlled_execution=controlled,
            selection=selection,
        )

        selected_index = self._selected_index(
            controlled=controlled,
            selected_candidate_id=(selection.selected_candidate_id),
        )

        selected_response = controlled.generation.responses[selected_index]

        selected_control = controlled.controls[selected_index]

        claim_lock = controlled.claim_lock_preparation.claim_lock

        selected_claim_lock_validation = selected_control.claim_lock_validation

        claim_lock_validation_audit = (
            ClaimLockValidationAuditSnapshot.model_validate(
                selected_claim_lock_validation.model_dump(mode="json")
            )
            if claim_lock is not None
            else None
        )

        history = self._history_service.record_rewrite(
            workspace_id=workspace_id,
            user_id=user_id,
            request=request,
            response=selected_response,
            voice_profile_id=(voice_guidance.profile_id if voice_guidance is not None else None),
            voice_guidance_version=(
                voice_guidance.guidance_version if voice_guidance is not None else None
            ),
            voice_analysis_snapshot=(
                voice_guidance.analysis_snapshot if voice_guidance is not None else None
            ),
            claim_lock_snapshot=claim_lock,
            claim_lock_validation=(claim_lock_validation_audit),
            claim_lock_enforcement_mode=(
                claim_lock_enforcement_mode if claim_lock is not None else None
            ),
            candidate_audit_snapshot=(audit_snapshot),
        )

        return MultiCandidateWorkspaceRewriteResult(
            selected_response=selected_response,
            history=history,
            candidate_set=(controlled.generation.candidate_set),
            diff_set=diff_set,
            controls=controlled.controls,
            selection=selection,
            audit_snapshot=audit_snapshot,
            claim_lock_preparation=(controlled.claim_lock_preparation),
            selected_claim_lock_validation=(selected_claim_lock_validation),
            voice_guidance=voice_guidance,
        )

    def _build_voice_guidance(
        self,
        *,
        workspace_id: str,
        user_id: str,
        voice_profile_id: str | None,
    ) -> VoiceRewriteGuidance | None:
        if voice_profile_id is None:
            return None

        if self._voice_guidance_service is None or self._voice_provider is None:
            raise MultiCandidateVoiceUnavailableError(
                "voice-aware multi-candidate rewrite orchestration is unavailable"
            )

        return self._voice_guidance_service.build_guidance(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=voice_profile_id,
        )

    def _execute_controlled(
        self,
        *,
        request: RewriteRequest,
        plan: CandidateGenerationPlan,
        voice_guidance: VoiceRewriteGuidance | None,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ],
        claim_lock_enforcement_mode: (ClaimLockEnforcementMode),
    ) -> ControlledCandidateGenerationExecution:
        if voice_guidance is None:
            return self._controlled_orchestrator.execute(
                request=request,
                plan=plan,
                explicit_protected_terms=(explicit_protected_terms),
                claim_lock_enforcement_mode=(claim_lock_enforcement_mode),
            )

        if self._voice_provider is None:
            raise MultiCandidateVoiceUnavailableError(
                "voice-aware multi-candidate rewrite orchestration is unavailable"
            )

        with self._voice_provider.use_guidance(voice_guidance):
            return self._controlled_orchestrator.execute(
                request=request,
                plan=plan,
                explicit_protected_terms=(explicit_protected_terms),
                claim_lock_enforcement_mode=(claim_lock_enforcement_mode),
            )

    @staticmethod
    def _selected_index(
        *,
        controlled: ControlledCandidateGenerationExecution,
        selected_candidate_id: str,
    ) -> int:
        for index, candidate in enumerate(controlled.generation.candidate_set.candidates):
            if candidate.candidate_id == selected_candidate_id:
                return index

        raise RuntimeError("selected candidate is not present in controlled candidate generation")
