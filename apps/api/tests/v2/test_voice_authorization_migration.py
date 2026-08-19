from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.v2.api.dependencies import V2Services
from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.v2.domain.models import VoiceSourceSample


def _create_voice_fixture() -> tuple[
    V2Services,
    str,
    str,
    str,
]:
    services = V2Services()

    owner = services.workspace.create_user(
        email=f"voice-owner-{uuid4().hex}@example.com",
        display_name="Voice Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=owner.user_id,
        name="Voice Authorization Workspace",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace.workspace_id,
        user_id=owner.user_id,
        name="Primary Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id="voice-auth-sample",
                text=(
                    "I keep communication clear and practical. "
                    "I explain the relevant context before the "
                    "next step, and I document the outcome so "
                    "the decision remains easy to follow."
                ),
            ),
        ),
    )

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace.workspace_id,
        user_id=owner.user_id,
        profile_id=profile.profile_id,
    )

    return (
        services,
        owner.user_id,
        workspace.workspace_id,
        analyzed.profile.profile_id,
    )


def _enterprise_only_user(
    services: V2Services,
    *,
    workspace_id: str,
    role: EnterpriseWorkspaceRole,
) -> str:
    user = services.workspace.create_user(
        email=f"voice-{role.value}-{uuid4().hex}@example.com",
        display_name=f"Voice {role.value}",
    )

    enterprise_workspace = (
        services.enterprise_authorization.workspaces.get(
            workspace_id
        )
    )

    assert enterprise_workspace is not None

    now = datetime.now(UTC)

    services.enterprise_authorization.memberships.create(
        EnterpriseWorkspaceMembership(
            membership_id=(
                f"voice-membership-{role.value}-{uuid4().hex}"
            ),
            organization_id=(
                enterprise_workspace.organization_id
            ),
            workspace_id=workspace_id,
            user_id=user.user_id,
            role=role,
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(PermissionError):
        services.workspace.require_membership(
            workspace_id=workspace_id,
            user_id=user.user_id,
        )

    return user.user_id


def test_production_voice_profile_service_uses_enterprise_gate() -> None:
    services = V2Services()

    assert (
        services.voice_profiles._authorization_gate
        is services.workspace_authorization
    )


def test_viewer_can_read_but_cannot_use_or_manage_voice() -> None:
    services, _, workspace_id, profile_id = (
        _create_voice_fixture()
    )

    viewer_id = _enterprise_only_user(
        services,
        workspace_id=workspace_id,
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    profile = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=viewer_id,
        profile_id=profile_id,
    )

    assert profile.profile_id == profile_id

    listed = services.voice_profiles.list_profiles(
        workspace_id=workspace_id,
        user_id=viewer_id,
    )

    assert any(
        item.profile_id == profile_id
        for item in listed
    )

    with pytest.raises(PermissionError):
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=viewer_id,
            profile_id=profile_id,
        )

    with pytest.raises(PermissionError):
        services.voice_profiles.create_profile(
            workspace_id=workspace_id,
            user_id=viewer_id,
            name="Forbidden Viewer Voice",
        )


def test_reviewer_can_read_but_cannot_use_voice() -> None:
    services, _, workspace_id, profile_id = (
        _create_voice_fixture()
    )

    reviewer_id = _enterprise_only_user(
        services,
        workspace_id=workspace_id,
        role=EnterpriseWorkspaceRole.REVIEWER,
    )

    profile = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=reviewer_id,
        profile_id=profile_id,
    )

    assert profile.profile_id == profile_id

    with pytest.raises(PermissionError):
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=reviewer_id,
            profile_id=profile_id,
        )


def test_editor_can_use_but_cannot_manage_voice() -> None:
    services, _, workspace_id, profile_id = (
        _create_voice_fixture()
    )

    editor_id = _enterprise_only_user(
        services,
        workspace_id=workspace_id,
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    guidance = (
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=editor_id,
            profile_id=profile_id,
        )
    )

    assert guidance.profile_id == profile_id

    with pytest.raises(PermissionError):
        services.voice_profiles.create_profile(
            workspace_id=workspace_id,
            user_id=editor_id,
            name="Forbidden Editor Voice",
        )

    current = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=editor_id,
        profile_id=profile_id,
    )

    candidate = current.model_copy(
        update={"name": "Forbidden Editor Update"},
    )

    with pytest.raises(PermissionError):
        services.voice_profiles.update_profile(
            workspace_id=workspace_id,
            user_id=editor_id,
            profile=candidate,
        )

    with pytest.raises(PermissionError):
        services.voice_profiles.analyze_profile(
            workspace_id=workspace_id,
            user_id=editor_id,
            profile_id=profile_id,
        )

    with pytest.raises(PermissionError):
        services.voice_profiles.archive_profile(
            workspace_id=workspace_id,
            user_id=editor_id,
            profile_id=profile_id,
        )


def test_admin_can_manage_voice_without_legacy_membership() -> None:
    services, _, workspace_id, _ = (
        _create_voice_fixture()
    )

    admin_id = _enterprise_only_user(
        services,
        workspace_id=workspace_id,
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_id,
        user_id=admin_id,
        name="Admin Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id="admin-sample",
                text=(
                    "I communicate decisions clearly and "
                    "preserve the context required to act."
                ),
            ),
        ),
    )

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=admin_id,
        profile_id=profile.profile_id,
    )

    candidate = analyzed.profile.model_copy(
        update={"name": "Admin Voice Updated"},
    )

    updated = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=admin_id,
        profile=candidate,
    )

    assert updated.name == "Admin Voice Updated"

    guidance = (
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_id,
            user_id=admin_id,
            profile_id=profile.profile_id,
        )
    )

    assert guidance.profile_id == profile.profile_id

    archived = services.voice_profiles.archive_profile(
        workspace_id=workspace_id,
        user_id=admin_id,
        profile_id=profile.profile_id,
    )

    assert archived.profile_id == profile.profile_id
    assert archived.status.value == "archived"
