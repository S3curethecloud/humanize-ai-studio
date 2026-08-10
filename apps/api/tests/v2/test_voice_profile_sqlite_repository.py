from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.v2.domain.models import (
    UserRecord,
    VoiceConcision,
    VoiceDirectness,
    VoiceFormality,
    VoiceProfileRecord,
    VoiceProfileStatus,
    VoiceSourceSample,
    VoiceStyleAttributes,
    VoiceWarmth,
    WorkspaceRecord,
)
from app.v2.repositories.interfaces import (
    VoiceProfileRepository,
)
from app.v2.repositories.sqlite import (
    SQLiteUserRepository,
    SQLiteVoiceProfileRepository,
    SQLiteWorkspaceRepository,
)


def _prepare_workspace(
    database_path: Path,
    *,
    user_id: str = "user_1",
    workspace_id: str = "workspace_1",
) -> None:
    users = SQLiteUserRepository(database_path)
    workspaces = SQLiteWorkspaceRepository(database_path)

    users.create(
        UserRecord(
            user_id=user_id,
            email=f"{user_id}@example.com",
            display_name=user_id,
        )
    )

    workspaces.create(
        WorkspaceRecord(
            workspace_id=workspace_id,
            name=workspace_id,
            created_by_user_id=user_id,
        )
    )


def _profile(
    *,
    profile_id: str,
    workspace_id: str = "workspace_1",
    user_id: str = "user_1",
    name: str = "Professional Voice",
    updated_at: datetime | None = None,
    status: VoiceProfileStatus = (VoiceProfileStatus.ACTIVE),
) -> VoiceProfileRecord:
    return VoiceProfileRecord(
        profile_id=profile_id,
        workspace_id=workspace_id,
        created_by_user_id=user_id,
        name=name,
        description="Enterprise writing voice",
        status=status,
        source_samples=(
            VoiceSourceSample(
                sample_id=f"{profile_id}_sample",
                text=("I prefer clear, direct technical communication."),
                label="technical sample",
            ),
        ),
        style_attributes=VoiceStyleAttributes(
            formality=VoiceFormality.FORMAL,
            directness=VoiceDirectness.DIRECT,
            warmth=VoiceWarmth.WARM,
            concision=VoiceConcision.CONCISE,
        ),
        updated_at=(updated_at if updated_at is not None else datetime.now(UTC)),
    )


def test_sqlite_voice_repository_matches_contract(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    repository: VoiceProfileRepository = SQLiteVoiceProfileRepository(database_path)

    profile = _profile(profile_id="voice_1")

    repository.create(profile)

    assert repository.get(profile.profile_id) == profile


def test_sqlite_voice_profile_survives_reopen(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    first = SQLiteVoiceProfileRepository(database_path)

    profile = _profile(profile_id="voice_1")

    first.create(profile)

    second = SQLiteVoiceProfileRepository(database_path)

    assert second.get(profile.profile_id) == profile


def test_sqlite_duplicate_voice_profile_is_rejected(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    repository = SQLiteVoiceProfileRepository(database_path)

    profile = _profile(profile_id="voice_duplicate")

    repository.create(profile)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(profile)


def test_sqlite_voice_listing_is_workspace_scoped(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"

    _prepare_workspace(
        database_path,
        user_id="user_1",
        workspace_id="workspace_1",
    )
    _prepare_workspace(
        database_path,
        user_id="user_2",
        workspace_id="workspace_2",
    )

    repository = SQLiteVoiceProfileRepository(database_path)

    first = _profile(
        profile_id="voice_1",
        workspace_id="workspace_1",
        user_id="user_1",
    )
    second = _profile(
        profile_id="voice_2",
        workspace_id="workspace_2",
        user_id="user_2",
    )

    repository.create(first)
    repository.create(second)

    assert repository.list_for_workspace(workspace_id="workspace_1") == (first,)


def test_sqlite_voice_profiles_order_by_updated_at(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    repository = SQLiteVoiceProfileRepository(database_path)

    now = datetime.now(UTC)

    older = _profile(
        profile_id="voice_old",
        updated_at=now - timedelta(minutes=5),
    )
    newer = _profile(
        profile_id="voice_new",
        updated_at=now,
    )

    repository.create(older)
    repository.create(newer)

    assert repository.list_for_workspace(workspace_id="workspace_1") == (
        newer,
        older,
    )


def test_sqlite_voice_listing_honors_limit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    repository = SQLiteVoiceProfileRepository(database_path)

    now = datetime.now(UTC)

    repository.create(
        _profile(
            profile_id="voice_1",
            updated_at=now,
        )
    )
    repository.create(
        _profile(
            profile_id="voice_2",
            updated_at=now - timedelta(minutes=1),
        )
    )

    records = repository.list_for_workspace(
        workspace_id="workspace_1",
        limit=1,
    )

    assert len(records) == 1
    assert records[0].profile_id == "voice_1"


def test_sqlite_voice_profile_update_persists(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    repository = SQLiteVoiceProfileRepository(database_path)

    original = _profile(
        profile_id="voice_1",
        name="Original Voice",
    )
    repository.create(original)

    updated = original.model_copy(
        update={
            "name": "Updated Voice",
            "status": VoiceProfileStatus.ARCHIVED,
            "source_samples": (
                VoiceSourceSample(
                    sample_id="replacement_sample",
                    text="Updated source sample.",
                    label="updated",
                ),
            ),
            "updated_at": datetime.now(UTC) + timedelta(seconds=1),
        }
    )

    repository.update(updated)

    reopened = SQLiteVoiceProfileRepository(database_path)

    assert reopened.get(original.profile_id) == updated


def test_sqlite_voice_update_rejects_unknown_profile(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"
    _prepare_workspace(database_path)

    repository = SQLiteVoiceProfileRepository(database_path)

    with pytest.raises(
        ValueError,
        match="Unknown voice profile",
    ):
        repository.update(_profile(profile_id="voice_missing"))


def test_sqlite_voice_profile_cannot_move_workspaces(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice.db"

    _prepare_workspace(
        database_path,
        user_id="user_1",
        workspace_id="workspace_1",
    )
    _prepare_workspace(
        database_path,
        user_id="user_2",
        workspace_id="workspace_2",
    )

    repository = SQLiteVoiceProfileRepository(database_path)

    original = _profile(profile_id="voice_1")
    repository.create(original)

    moved = original.model_copy(
        update={
            "workspace_id": "workspace_2",
            "created_by_user_id": "user_2",
        }
    )

    with pytest.raises(
        ValueError,
        match="workspace cannot be changed",
    ):
        repository.update(moved)

    assert repository.get(original.profile_id) == original
