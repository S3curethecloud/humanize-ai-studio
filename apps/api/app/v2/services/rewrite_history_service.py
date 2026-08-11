from __future__ import annotations

from uuid import uuid4

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.repositories.interfaces import (
    RewriteHistoryRepository,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


class RewriteHistoryService:
    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        history: RewriteHistoryRepository,
    ) -> None:
        self._workspace_service = workspace_service
        self._history = history

    def record_rewrite(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        response: RewriteResponse,
        voice_profile_id: str | None = None,
        voice_guidance_version: str | None = None,
    ) -> RewriteHistoryRecord:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        record = RewriteHistoryRecord(
            rewrite_id=(f"history_{uuid4().hex}"),
            workspace_id=workspace_id,
            user_id=user_id,
            trace_id=response.trace_id,
            source_text=response.source_text,
            rewritten_text=(response.rewritten_text),
            document_type=(request.document_type.value),
            audience=request.audience,
            tone=request.tone,
            intensity=request.intensity.value,
            provider_name=(response.provider_name),
            model_name=response.model_name,
            prompt_version=(response.prompt_version),
            voice_profile_id=voice_profile_id,
            voice_guidance_version=voice_guidance_version,
            fallback_used=(response.provider_execution.fallback_used),
            verification_decision=(response.verification.decision.value),
            editorial_quality_decision=(response.editorial_quality.decision.value),
        )

        return self._history.create(record)

    def list_workspace_history(
        self,
        *,
        workspace_id: str,
        user_id: str,
        limit: int = 50,
    ) -> tuple[RewriteHistoryRecord, ...]:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        return self._history.list_for_workspace(
            workspace_id=workspace_id,
            limit=limit,
        )
