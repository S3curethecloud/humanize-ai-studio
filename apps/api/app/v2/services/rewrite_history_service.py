from __future__ import annotations

from uuid import uuid4

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.candidate_audit import (
    CandidateAuditSnapshot,
)
from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
)
from app.v2.domain.claim_lock_audit import (
    ClaimLockValidationAuditSnapshot,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    VoiceRewriteAnalysisBinding,
    VoiceRewriteAnalysisSnapshot,
)
from app.v2.repositories.interfaces import (
    RewriteHistoryRepository,
)
from app.v2.services.voice_audit_authenticator import (
    VoiceAuditAuthenticator,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class RewriteHistoryService:
    def __init__(
        self,
        *,
        history: RewriteHistoryRepository,
        voice_audit_authenticator: VoiceAuditAuthenticator | None = None,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._history = history
        self._voice_audit_authenticator = voice_audit_authenticator
        self._authorization_gate = authorization_gate

    def record_rewrite(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        response: RewriteResponse,
        voice_profile_id: str | None = None,
        voice_guidance_version: str | None = None,
        voice_analysis_snapshot: VoiceRewriteAnalysisSnapshot | None = None,
        claim_lock_snapshot: ClaimLock | None = None,
        claim_lock_validation: ClaimLockValidationAuditSnapshot | None = None,
        claim_lock_enforcement_mode: ClaimLockEnforcementMode | None = None,
        candidate_audit_snapshot: CandidateAuditSnapshot | None = None,
    ) -> RewriteHistoryRecord:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.REWRITE_EXECUTE,
        )

        voice_analysis_binding = (
            VoiceRewriteAnalysisBinding.from_snapshot(voice_analysis_snapshot)
            if voice_analysis_snapshot is not None
            else None
        )

        voice_analysis_authenticity = (
            self._voice_audit_authenticator.sign(voice_analysis_snapshot)
            if (voice_analysis_snapshot is not None and self._voice_audit_authenticator is not None)
            else None
        )

        candidate_set_id = (
            candidate_audit_snapshot.candidate_set_id
            if candidate_audit_snapshot is not None
            else None
        )

        selected_candidate_id = (
            candidate_audit_snapshot.selected_candidate_id
            if candidate_audit_snapshot is not None
            else None
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
            voice_analysis_snapshot=voice_analysis_snapshot,
            voice_analysis_binding=voice_analysis_binding,
            voice_analysis_authenticity=voice_analysis_authenticity,
            claim_lock_snapshot=claim_lock_snapshot,
            claim_lock_validation=claim_lock_validation,
            claim_lock_enforcement_mode=claim_lock_enforcement_mode,
            candidate_set_id=candidate_set_id,
            candidate_audit_snapshot=candidate_audit_snapshot,
            selected_candidate_id=selected_candidate_id,
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
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.HISTORY_READ,
        )

        records = self._history.list_for_workspace(
            workspace_id=workspace_id,
            limit=limit,
        )

        for record in records:
            self._verify_voice_authenticity(record)

        return records

    def _verify_voice_authenticity(
        self,
        record: RewriteHistoryRecord,
    ) -> None:
        authenticator = self._voice_audit_authenticator

        if authenticator is None:
            return

        snapshot = record.voice_analysis_snapshot
        authenticity = record.voice_analysis_authenticity

        if snapshot is None:
            if authenticity is not None:
                raise ValueError("non-voice history must not contain voice analysis authenticity")

            return

        if authenticity is None:
            raise ValueError("voice analysis authenticity is required")

        if not authenticator.verify(
            snapshot=snapshot,
            authenticity=authenticity,
        ):
            raise ValueError("voice analysis authenticity verification failed")
