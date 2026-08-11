from __future__ import annotations

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    VoiceRewriteAnalysisSnapshot,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
    ClaimLockValidator,
    ClaimLockViolationError,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


class WorkspaceRewriteResult:
    def __init__(
        self,
        *,
        response: RewriteResponse,
        history: RewriteHistoryRecord,
        claim_lock_preparation: ClaimLockPreparationResult,
        claim_lock_validation: ClaimLockValidationResult,
    ) -> None:
        self.response = response
        self.history = history
        self.claim_lock_preparation = claim_lock_preparation
        self.claim_lock_validation = claim_lock_validation


class WorkspaceRewriteService:
    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        history_service: RewriteHistoryService,
        workflow: RewriteWorkflow,
        claim_lock_preparation_service: (ClaimLockPreparationService | None) = None,
        claim_lock_validator: (ClaimLockValidator | None) = None,
    ) -> None:
        self._workspace_service = workspace_service
        self._history_service = history_service
        self._workflow = workflow
        self._claim_lock_preparation_service = (
            claim_lock_preparation_service or ClaimLockPreparationService()
        )
        self._claim_lock_validator = claim_lock_validator or ClaimLockValidator()

    def execute(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        voice_profile_id: str | None = None,
        voice_guidance_version: str | None = None,
        voice_analysis_snapshot: VoiceRewriteAnalysisSnapshot | None = None,
        claim_lock_enforcement_mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
    ) -> WorkspaceRewriteResult:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        claim_lock_preparation = self._claim_lock_preparation_service.prepare(
            text=request.text,
            enforcement_mode=(claim_lock_enforcement_mode),
        )

        response = self._workflow.execute(request)

        claim_lock_validation = self._claim_lock_validator.validate(
            claim_lock=(claim_lock_preparation.claim_lock),
            rewritten_text=(response.rewritten_text),
        )

        if (
            response.verification.decision is not ReleaseDecision.FAIL
            and claim_lock_enforcement_mode is ClaimLockEnforcementMode.STRICT
            and claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION
        ):
            raise ClaimLockViolationError(claim_lock_validation)

        history = self._history_service.record_rewrite(
            workspace_id=workspace_id,
            user_id=user_id,
            request=request,
            response=response,
            voice_profile_id=voice_profile_id,
            voice_guidance_version=voice_guidance_version,
            voice_analysis_snapshot=voice_analysis_snapshot,
        )

        return WorkspaceRewriteResult(
            response=response,
            history=history,
            claim_lock_preparation=(claim_lock_preparation),
            claim_lock_validation=(claim_lock_validation),
        )
