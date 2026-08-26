from __future__ import annotations

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    EnterpriseClaimLockRuntimeContext,
)
from app.v2.domain.voice_rewrite import (
    VoiceRewriteGuidance,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationResult,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceRewriteGuidanceService,
)
from app.v2.services.workspace_rewrite_service import (
    WorkspaceRewriteService,
)


class VoiceAwareWorkspaceRewriteResult:
    def __init__(
        self,
        *,
        response: RewriteResponse,
        history: RewriteHistoryRecord,
        guidance: VoiceRewriteGuidance,
        claim_lock_preparation: ClaimLockPreparationResult,
        claim_lock_validation: ClaimLockValidationResult,
        claim_lock_runtime_context: (
            EnterpriseClaimLockRuntimeContext | None
        ) = None,
    ) -> None:
        self.response = response
        self.history = history
        self.guidance = guidance
        self.claim_lock_preparation = claim_lock_preparation
        self.claim_lock_validation = claim_lock_validation
        self.claim_lock_runtime_context = (
            claim_lock_runtime_context
        )


class VoiceAwareWorkspaceRewriteService:
    def __init__(
        self,
        *,
        rewrite_service: WorkspaceRewriteService,
        guidance_service: VoiceRewriteGuidanceService,
        provider: VoiceAwareRewriteProvider,
    ) -> None:
        self._rewrite_service = rewrite_service
        self._guidance_service = guidance_service
        self._provider = provider

    def execute(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
        request: RewriteRequest,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: (
            ClaimLockEnforcementMode | None
        ) = None,
    ) -> VoiceAwareWorkspaceRewriteResult:
        guidance = self._guidance_service.build_guidance(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )

        with self._provider.use_guidance(guidance):
            result = self._rewrite_service.execute(
                workspace_id=workspace_id,
                user_id=user_id,
                request=request,
                voice_profile_id=guidance.profile_id,
                voice_guidance_version=guidance.guidance_version,
                voice_analysis_snapshot=guidance.analysis_snapshot,
                explicit_protected_terms=explicit_protected_terms,
                claim_lock_enforcement_mode=claim_lock_enforcement_mode,
            )

        return VoiceAwareWorkspaceRewriteResult(
            response=result.response,
            history=result.history,
            guidance=guidance,
            claim_lock_preparation=(result.claim_lock_preparation),
            claim_lock_validation=(result.claim_lock_validation),
            claim_lock_runtime_context=(
                result.claim_lock_runtime_context
            ),
        )
