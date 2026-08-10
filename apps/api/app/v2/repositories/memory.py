from __future__ import annotations

from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    VoiceProfileRecord,
    WorkspaceMembership,
    WorkspaceRecord,
)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}

    def create(
        self,
        user: UserRecord,
    ) -> UserRecord:
        self._users[user.user_id] = user
        return user

    def get(
        self,
        user_id: str,
    ) -> UserRecord | None:
        return self._users.get(user_id)


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._workspaces: dict[
            str,
            WorkspaceRecord,
        ] = {}

    def create(
        self,
        workspace: WorkspaceRecord,
    ) -> WorkspaceRecord:
        self._workspaces[workspace.workspace_id] = workspace
        return workspace

    def get(
        self,
        workspace_id: str,
    ) -> WorkspaceRecord | None:
        return self._workspaces.get(workspace_id)


class InMemoryMembershipRepository:
    def __init__(self) -> None:
        self._memberships: dict[
            tuple[str, str],
            WorkspaceMembership,
        ] = {}

    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        key = (
            membership.workspace_id,
            membership.user_id,
        )
        self._memberships[key] = membership
        return membership

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceMembership | None:
        return self._memberships.get(
            (
                workspace_id,
                user_id,
            )
        )


class InMemoryRewriteHistoryRepository:
    def __init__(self) -> None:
        self._records: dict[
            str,
            RewriteHistoryRecord,
        ] = {}

    def create(
        self,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord:
        self._records[record.rewrite_id] = record
        return record

    def get(
        self,
        rewrite_id: str,
    ) -> RewriteHistoryRecord | None:
        return self._records.get(rewrite_id)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[RewriteHistoryRecord, ...]:
        records = tuple(
            record for record in self._records.values() if record.workspace_id == workspace_id
        )

        ordered = sorted(
            records,
            key=lambda record: record.created_at,
            reverse=True,
        )

        return tuple(ordered[:limit])


class InMemoryVoiceProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[
            str,
            VoiceProfileRecord,
        ] = {}

    def create(
        self,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord:
        if profile.profile_id in self._profiles:
            raise ValueError(f"Voice profile already exists: {profile.profile_id}")

        self._profiles[profile.profile_id] = profile
        return profile

    def get(
        self,
        profile_id: str,
    ) -> VoiceProfileRecord | None:
        return self._profiles.get(profile_id)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[VoiceProfileRecord, ...]:
        profiles = (
            profile for profile in self._profiles.values() if profile.workspace_id == workspace_id
        )

        ordered = sorted(
            profiles,
            key=lambda profile: profile.updated_at,
            reverse=True,
        )

        return tuple(ordered[:limit])

    def update(
        self,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord:
        existing = self._profiles.get(profile.profile_id)

        if existing is None:
            raise ValueError(f"Unknown voice profile: {profile.profile_id}")

        if existing.workspace_id != profile.workspace_id:
            raise ValueError("Voice profile workspace cannot be changed.")

        self._profiles[profile.profile_id] = profile
        return profile
