from __future__ import annotations

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.domain.voice_rewrite import (
    VoiceRewriteGuidance,
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
    ) -> None:
        self.response = response
        self.history = history
        self.guidance = guidance


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
            )

        return VoiceAwareWorkspaceRewriteResult(
            response=result.response,
            history=result.history,
            guidance=guidance,
        )
