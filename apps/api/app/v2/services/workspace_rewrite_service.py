from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.claim_lock_audit import (
    ClaimLockValidationAuditSnapshot,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    VoiceRewriteAnalysisSnapshot,
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
    ClaimLockViolationError,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseSingleRewriteQuotaAdmissionService,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.single_rewrite_observability import (
    SingleRewriteObservability,
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
        quota_admission: (EnterpriseSingleRewriteQuotaAdmissionService | None) = None,
        claim_lock_preparation_service: (ClaimLockPreparationService | None) = None,
        claim_lock_validator: (ClaimLockValidator | None) = None,
        observability: SingleRewriteObservability | None = None,
        duration_clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._workspace_service = workspace_service
        self._history_service = history_service
        self._workflow = workflow
        self._quota_admission = quota_admission
        self._observability = observability
        self._duration_clock = duration_clock
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
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
    ) -> WorkspaceRewriteResult:
        started_at = self._duration_clock()

        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        claim_lock_preparation = self._claim_lock_preparation_service.prepare(
            text=request.text,
            explicit_terms=explicit_protected_terms,
            enforcement_mode=claim_lock_enforcement_mode,
        )

        if self._quota_admission is not None:
            self._quota_admission.admit(
                workspace_id=workspace_id,
                request=request,
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

        claim_lock_validation_audit = (
            ClaimLockValidationAuditSnapshot.model_validate(
                claim_lock_validation.model_dump(mode="json")
            )
            if claim_lock_preparation.claim_lock is not None
            else None
        )

        history = self._history_service.record_rewrite(
            workspace_id=workspace_id,
            user_id=user_id,
            request=request,
            response=response,
            voice_profile_id=voice_profile_id,
            voice_guidance_version=voice_guidance_version,
            voice_analysis_snapshot=voice_analysis_snapshot,
            claim_lock_snapshot=(claim_lock_preparation.claim_lock),
            claim_lock_validation=(claim_lock_validation_audit),
            claim_lock_enforcement_mode=(
                claim_lock_enforcement_mode
                if claim_lock_preparation.claim_lock is not None
                else None
            ),
        )

        if self._observability is not None:
            duration_ms = max(
                0.0,
                (self._duration_clock() - started_at) * 1000.0,
            )

            self._observability.record_success(
                workspace_id=workspace_id,
                user_id=user_id,
                request=request,
                response=response,
                history=history,
                claim_lock_validation=(claim_lock_validation),
                duration_ms=duration_ms,
            )

        return WorkspaceRewriteResult(
            response=response,
            history=history,
            claim_lock_preparation=(claim_lock_preparation),
            claim_lock_validation=(claim_lock_validation),
        )
