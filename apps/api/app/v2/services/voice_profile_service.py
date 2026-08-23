from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.models import (
    VoiceAnalysisProvenance,
    VoiceAnalysisState,
    VoiceProfileAnalysisResult,
    VoiceProfileRecord,
    VoiceProfileStatus,
    VoiceSourceSample,
    VoiceStyleAttributes,
)
from app.v2.repositories.interfaces import (
    VoiceProfileRepository,
)
from app.v2.services.voice_dna_analyzer import (
    VoiceDNAAnalyzer,
)
from app.v2.services.voice_sample_fingerprint import (
    voice_sample_fingerprint,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class VoiceProfileLifecycleError(ValueError):
    pass


class VoiceProfileService:
    def __init__(
        self,
        *,
        profiles: VoiceProfileRepository,
        analyzer: VoiceDNAAnalyzer | None = None,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._profiles = profiles
        self._analyzer = analyzer if analyzer is not None else VoiceDNAAnalyzer()
        self._authorization_gate = authorization_gate

    def create_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        name: str,
        description: str | None = None,
        source_samples: tuple[
            VoiceSourceSample,
            ...,
        ] = (),
        style_attributes: (VoiceStyleAttributes | None) = None,
    ) -> VoiceProfileRecord:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_MANAGE,
        )

        now = datetime.now(UTC)

        profile = VoiceProfileRecord(
            profile_id=f"voice_{uuid4().hex}",
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            name=name,
            description=description,
            source_samples=source_samples,
            style_attributes=(
                style_attributes if style_attributes is not None else VoiceStyleAttributes()
            ),
            created_at=now,
            updated_at=now,
        )

        return self._profiles.create(profile)

    def get_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
    ) -> VoiceProfileRecord:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_READ,
        )

        return self._get_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )

    def get_profile_for_use(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
    ) -> VoiceProfileRecord:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_USE,
        )

        return self._get_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )

    def list_profiles(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_status: VoiceProfileStatus | None = None,
        limit: int = 50,
    ) -> tuple[VoiceProfileRecord, ...]:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_READ,
        )

        return self._profiles.list_for_workspace(
            workspace_id=workspace_id,
            profile_status=profile_status,
            limit=limit,
        )

    def update_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_MANAGE,
        )

        existing = self._get_profile(
            workspace_id=workspace_id,
            profile_id=profile.profile_id,
        )

        self._require_profile_workspace(
            profile=profile,
            workspace_id=workspace_id,
        )

        self._require_active_profile(
            existing,
            operation="update",
        )

        analysis_state = VoiceAnalysisState.NEVER_ANALYZED
        analysis_provenance = existing.analysis_provenance

        if analysis_provenance is not None:
            source_fingerprint = voice_sample_fingerprint(profile.source_samples)

            source_changed = source_fingerprint != analysis_provenance.source_fingerprint
            style_changed = profile.style_attributes != existing.style_attributes

            if (
                existing.analysis_state is VoiceAnalysisState.STALE
                or source_changed
                or style_changed
            ):
                analysis_state = VoiceAnalysisState.STALE
            else:
                analysis_state = VoiceAnalysisState.CURRENT

        updated = profile.model_copy(
            update={
                "analysis_state": analysis_state,
                "analysis_provenance": analysis_provenance,
                "updated_at": datetime.now(UTC),
            }
        )

        return self._profiles.update(updated)

    def analyze_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
    ) -> VoiceProfileAnalysisResult:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_MANAGE,
        )

        profile = self._get_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )

        self._require_active_profile(
            profile,
            operation="analyze",
        )

        analysis = self._analyzer.analyze(profile.source_samples)

        analyzed_at = datetime.now(UTC)

        provenance = VoiceAnalysisProvenance(
            analyzer_version=analysis.evidence.analyzer_version,
            analyzed_at=analyzed_at,
            source_sample_ids=tuple(sample.sample_id for sample in profile.source_samples),
            source_fingerprint=voice_sample_fingerprint(profile.source_samples),
            sample_count=analysis.evidence.sample_count,
            sufficiency=analysis.evidence.sufficiency,
            consistency=(analysis.evidence.sample_consistency.classification),
        )

        updated = profile.model_copy(
            update={
                "style_attributes": analysis.style_attributes,
                "analysis_state": VoiceAnalysisState.CURRENT,
                "analysis_provenance": provenance,
                "updated_at": analyzed_at,
            }
        )

        persisted = self._profiles.update(updated)

        return VoiceProfileAnalysisResult(
            profile=persisted,
            evidence=analysis.evidence,
        )

    def archive_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
    ) -> VoiceProfileRecord:
        self._require_permission(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.VOICE_MANAGE,
        )

        profile = self._get_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )

        if profile.status is VoiceProfileStatus.ARCHIVED:
            return profile

        archived = profile.model_copy(
            update={
                "status": VoiceProfileStatus.ARCHIVED,
                "updated_at": datetime.now(UTC),
            }
        )

        return self._profiles.update(archived)

    def _require_permission(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> None:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=permission,
        )

    def _get_profile(
        self,
        *,
        workspace_id: str,
        profile_id: str,
    ) -> VoiceProfileRecord:
        profile = self._profiles.get(profile_id)

        if profile is None:
            raise ValueError(f"Unknown voice profile: {profile_id}")

        self._require_profile_workspace(
            profile=profile,
            workspace_id=workspace_id,
        )

        return profile

    def _require_active_profile(
        self,
        profile: VoiceProfileRecord,
        *,
        operation: str,
    ) -> None:
        if profile.status is not VoiceProfileStatus.ACTIVE:
            raise VoiceProfileLifecycleError(
                f"Archived voice profiles cannot be used for {operation}."
            )

    def _require_profile_workspace(
        self,
        *,
        profile: VoiceProfileRecord,
        workspace_id: str,
    ) -> None:
        if profile.workspace_id != workspace_id:
            raise PermissionError("Voice profile does not belong to the requested workspace.")
