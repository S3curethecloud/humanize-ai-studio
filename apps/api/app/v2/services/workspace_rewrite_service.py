from __future__ import annotations

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    VoiceRewriteAnalysisSnapshot,
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
    ) -> None:
        self.response = response
        self.history = history


class WorkspaceRewriteService:
    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        history_service: RewriteHistoryService,
        workflow: RewriteWorkflow,
    ) -> None:
        self._workspace_service = workspace_service
        self._history_service = history_service
        self._workflow = workflow

    def execute(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        voice_profile_id: str | None = None,
        voice_guidance_version: str | None = None,
        voice_analysis_snapshot: VoiceRewriteAnalysisSnapshot | None = None,
    ) -> WorkspaceRewriteResult:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        response = self._workflow.execute(request)

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
        )
