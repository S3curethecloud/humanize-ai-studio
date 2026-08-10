from datetime import UTC, datetime, timedelta

import pytest

from app.v2.domain.models import (
    VoiceProfileRecord,
    VoiceProfileStatus,
)
from app.v2.repositories.interfaces import (
    VoiceProfileRepository,
)
from app.v2.repositories.memory import (
    InMemoryVoiceProfileRepository,
)


def _profile(
    *,
    profile_id: str,
    workspace_id: str = "workspace_1",
    name: str = "Professional Voice",
    status: VoiceProfileStatus = VoiceProfileStatus.ACTIVE,
    updated_at: datetime | None = None,
) -> VoiceProfileRecord:
    return VoiceProfileRecord(
        profile_id=profile_id,
        workspace_id=workspace_id,
        created_by_user_id="user_1",
        name=name,
        status=status,
        updated_at=(updated_at if updated_at is not None else datetime.now(UTC)),
    )


def test_memory_voice_repository_matches_contract() -> None:
    repository: VoiceProfileRepository = InMemoryVoiceProfileRepository()

    profile = _profile(profile_id="voice_1")

    repository.create(profile)

    assert repository.get(profile.profile_id) == profile


def test_duplicate_voice_profile_id_is_rejected() -> None:
    repository = InMemoryVoiceProfileRepository()

    profile = _profile(profile_id="voice_duplicate")

    repository.create(profile)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(profile)


def test_voice_profile_listing_is_workspace_scoped() -> None:
    repository = InMemoryVoiceProfileRepository()

    first = _profile(
        profile_id="voice_1",
        workspace_id="workspace_1",
    )
    second = _profile(
        profile_id="voice_2",
        workspace_id="workspace_2",
    )

    repository.create(first)
    repository.create(second)

    records = repository.list_for_workspace(workspace_id="workspace_1")

    assert records == (first,)


def test_voice_profiles_are_ordered_by_updated_at() -> None:
    repository = InMemoryVoiceProfileRepository()

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

    records = repository.list_for_workspace(workspace_id="workspace_1")

    assert records == (
        newer,
        older,
    )


def test_voice_profile_listing_honors_limit() -> None:
    repository = InMemoryVoiceProfileRepository()

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


def test_voice_profile_update_replaces_existing_record() -> None:
    repository = InMemoryVoiceProfileRepository()

    original = _profile(
        profile_id="voice_1",
        name="Original Voice",
    )
    repository.create(original)

    updated = original.model_copy(
        update={
            "name": "Updated Voice",
            "updated_at": datetime.now(UTC) + timedelta(seconds=1),
        }
    )

    repository.update(updated)

    assert repository.get(original.profile_id) == updated


def test_voice_profile_update_rejects_unknown_profile() -> None:
    repository = InMemoryVoiceProfileRepository()

    profile = _profile(profile_id="voice_missing")

    with pytest.raises(
        ValueError,
        match="Unknown voice profile",
    ):
        repository.update(profile)


def test_voice_profile_cannot_move_between_workspaces() -> None:
    repository = InMemoryVoiceProfileRepository()

    original = _profile(
        profile_id="voice_1",
        workspace_id="workspace_1",
    )
    repository.create(original)

    moved = original.model_copy(
        update={
            "workspace_id": "workspace_2",
            "updated_at": datetime.now(UTC),
        }
    )

    with pytest.raises(
        ValueError,
        match="workspace cannot be changed",
    ):
        repository.update(moved)

    assert repository.get(original.profile_id) == original


def test_archived_voice_profile_remains_retrievable() -> None:
    repository = InMemoryVoiceProfileRepository()

    archived = _profile(
        profile_id="voice_archived",
        status=VoiceProfileStatus.ARCHIVED,
    )

    repository.create(archived)

    assert repository.get(archived.profile_id) == archived

    assert repository.list_for_workspace(workspace_id=archived.workspace_id) == (archived,)
