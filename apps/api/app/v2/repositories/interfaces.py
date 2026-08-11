from __future__ import annotations

from typing import Protocol

from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    VoiceProfileRecord,
    VoiceProfileStatus,
    WorkspaceMembership,
    WorkspaceRecord,
)


class UserRepository(Protocol):
    def create(
        self,
        user: UserRecord,
    ) -> UserRecord: ...

    def get(
        self,
        user_id: str,
    ) -> UserRecord | None: ...


class WorkspaceRepository(Protocol):
    def create(
        self,
        workspace: WorkspaceRecord,
    ) -> WorkspaceRecord: ...

    def get(
        self,
        workspace_id: str,
    ) -> WorkspaceRecord | None: ...


class MembershipRepository(Protocol):
    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership: ...

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceMembership | None: ...


class RewriteHistoryRepository(Protocol):
    def create(
        self,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord: ...

    def get(
        self,
        rewrite_id: str,
    ) -> RewriteHistoryRecord | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[RewriteHistoryRecord, ...]: ...


class VoiceProfileRepository(Protocol):
    def create(
        self,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord: ...

    def get(
        self,
        profile_id: str,
    ) -> VoiceProfileRecord | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        profile_status: VoiceProfileStatus | None = None,
        limit: int = 50,
    ) -> tuple[VoiceProfileRecord, ...]: ...

    def update(
        self,
        profile: VoiceProfileRecord,
    ) -> VoiceProfileRecord: ...
