from pathlib import Path

import pytest

from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.models import (
    VoiceProfileStatus,
    VoiceSourceSample,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _memory_services() -> V2Services:
    return V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=(
            V2PersistenceSettings(
                backend=(PersistenceBackend.MEMORY),
                sqlite_path=None,
                database_url=None,
            )
        ),
    )


def _create_workspace(
    services: V2Services,
    *,
    email: str = "owner@example.com",
) -> tuple[str, str]:
    user = services.workspace.create_user(
        email=email,
        display_name="Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=user.user_id,
        name="Voice Workspace",
    )

    return (
        user.user_id,
        workspace.workspace_id,
    )


def test_voice_profile_service_creates_profile() -> None:
    services = _memory_services()

    user_id, workspace_id = _create_workspace(services)

    sample = VoiceSourceSample(
        sample_id="sample_1",
        text="I write directly and clearly.",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        name="Primary Voice",
        source_samples=(sample,),
    )

    assert profile.workspace_id == workspace_id
    assert profile.created_by_user_id == user_id
    assert profile.source_samples == (sample,)


def test_voice_profile_creation_requires_membership() -> None:
    services = _memory_services()

    owner_id, workspace_id = _create_workspace(services)

    other = services.workspace.create_user(
        email="other@example.com",
        display_name="Other",
    )

    assert owner_id != other.user_id

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_profiles.create_profile(
            workspace_id=workspace_id,
            user_id=other.user_id,
            name="Forbidden Voice",
        )


def test_voice_profile_get_enforces_workspace_boundary() -> None:
    services = _memory_services()

    user_one, workspace_one = _create_workspace(
        services,
        email="one@example.com",
    )
    user_two, workspace_two = _create_workspace(
        services,
        email="two@example.com",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_one,
        user_id=user_one,
        name="Workspace One Voice",
    )

    with pytest.raises(
        PermissionError,
        match="does not belong",
    ):
        services.voice_profiles.get_profile(
            workspace_id=workspace_two,
            user_id=user_two,
            profile_id=profile.profile_id,
        )


def test_voice_profile_list_is_workspace_scoped() -> None:
    services = _memory_services()

    user_one, workspace_one = _create_workspace(
        services,
        email="one@example.com",
    )
    user_two, workspace_two = _create_workspace(
        services,
        email="two@example.com",
    )

    first = services.voice_profiles.create_profile(
        workspace_id=workspace_one,
        user_id=user_one,
        name="First Voice",
    )

    services.voice_profiles.create_profile(
        workspace_id=workspace_two,
        user_id=user_two,
        name="Second Voice",
    )

    records = services.voice_profiles.list_profiles(
        workspace_id=workspace_one,
        user_id=user_one,
    )

    assert records == (first,)


def test_voice_profile_update_preserves_workspace() -> None:
    services = _memory_services()

    user_id, workspace_id = _create_workspace(services)

    original = services.voice_profiles.create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        name="Original Voice",
    )

    changed = original.model_copy(
        update={
            "name": "Updated Voice",
        }
    )

    updated = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=changed,
    )

    assert updated.name == "Updated Voice"
    assert updated.workspace_id == workspace_id


def test_voice_profile_archive_is_persistent() -> None:
    services = _memory_services()

    user_id, workspace_id = _create_workspace(services)

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        name="Archive Me",
    )

    archived = services.voice_profiles.archive_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile.profile_id,
    )

    assert archived.status is VoiceProfileStatus.ARCHIVED

    retrieved = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile.profile_id,
    )

    assert retrieved.status is VoiceProfileStatus.ARCHIVED


def test_sqlite_voice_profile_service_survives_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice-service.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    first = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    user_id, workspace_id = _create_workspace(first)

    profile = first.voice_profiles.create_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        name="Durable Voice",
    )

    second = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )

    retrieved = second.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile.profile_id,
    )

    assert retrieved == profile


def test_voice_profile_cannot_be_updated_through_another_workspace() -> None:
    services = _memory_services()

    user_one, workspace_one = _create_workspace(
        services,
        email="one@example.com",
    )
    user_two, workspace_two = _create_workspace(
        services,
        email="two@example.com",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_one,
        user_id=user_one,
        name="Protected Voice",
    )

    moved = profile.model_copy(
        update={
            "workspace_id": workspace_two,
        }
    )

    with pytest.raises(
        PermissionError,
        match="does not belong",
    ):
        services.voice_profiles.update_profile(
            workspace_id=workspace_two,
            user_id=user_two,
            profile=moved,
        )
