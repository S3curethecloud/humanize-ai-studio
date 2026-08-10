from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.v2.domain.models import (
    VoiceProfileRecord,
    VoiceProfileStatus,
    VoiceSourceSample,
    VoiceStyleAttributes,
)
from app.v2.repositories.interfaces import (
    VoiceProfileRepository,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


class VoiceProfileService:
    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        profiles: VoiceProfileRepository,
    ) -> None:
        self._workspace_service = workspace_service
        self._profiles = profiles

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
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
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
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        profile = self._profiles.get(profile_id)

        if profile is None:
            raise ValueError(f"Unknown voice profile: {profile_id}")

        self._require_profile_workspace(
            profile=profile,
            workspace_id=workspace_id,
        )

        return profile

    def list_profiles(
        self,
        *,
        workspace_id: str,
        user_id: str,
        limit: int = 50,
    ) -> tuple[VoiceProfileRecord, ...]:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        return self._profiles.list_for_workspace(
            workspace_id=workspace_id,
            limit=limit,
        )

    def update_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord:
        self._workspace_service.require_membership(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        existing = self._profiles.get(profile.profile_id)

        if existing is None:
            raise ValueError(f"Unknown voice profile: {profile.profile_id}")

        self._require_profile_workspace(
            profile=existing,
            workspace_id=workspace_id,
        )

        self._require_profile_workspace(
            profile=profile,
            workspace_id=workspace_id,
        )

        updated = profile.model_copy(
            update={
                "updated_at": datetime.now(UTC),
            }
        )

        return self._profiles.update(updated)

    def archive_profile(
        self,
        *,
        workspace_id: str,
        user_id: str,
        profile_id: str,
    ) -> VoiceProfileRecord:
        profile = self.get_profile(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )

        archived = profile.model_copy(
            update={
                "status": (VoiceProfileStatus.ARCHIVED),
                "updated_at": datetime.now(UTC),
            }
        )

        return self._profiles.update(archived)

    def _require_profile_workspace(
        self,
        *,
        profile: VoiceProfileRecord,
        workspace_id: str,
    ) -> None:
        if profile.workspace_id != workspace_id:
            raise PermissionError("Voice profile does not belong to the requested workspace.")
