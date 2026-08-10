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
    VoiceDirectness,
    VoiceSentenceLength,
    VoiceSourceSample,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _services(
    settings: V2PersistenceSettings,
) -> V2Services:
    return V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=settings,
    )


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _create_profile(
    services: V2Services,
) -> tuple[str, str, str]:
    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="Voice Workspace",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        name="Analyzed Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id="sample_1",
                text=("Ship the update today. Review the evidence now. Document the outcome."),
            ),
        ),
    )

    return (
        user.user_id,
        workspace.workspace_id,
        profile.profile_id,
    )


def test_analysis_updates_profile_attributes() -> None:
    services = _services(_memory_settings())

    user_id, workspace_id, profile_id = _create_profile(services)

    result = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    assert result.profile.style_attributes.sentence_length is VoiceSentenceLength.SHORT
    assert result.profile.style_attributes.directness is VoiceDirectness.DIRECT

    retrieved = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    assert retrieved.style_attributes == result.profile.style_attributes


def test_analysis_requires_workspace_membership() -> None:
    services = _services(_memory_settings())

    _, workspace_id, profile_id = _create_profile(services)

    outsider = services.workspace.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    with pytest.raises(
        PermissionError,
        match="not a member",
    ):
        services.voice_profiles.analyze_profile(
            workspace_id=workspace_id,
            user_id=outsider.user_id,
            profile_id=profile_id,
        )


def test_sqlite_analysis_survives_service_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice-analysis.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    first = _services(settings)

    user_id, workspace_id, profile_id = _create_profile(first)

    result = first.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    second = _services(settings)

    retrieved = second.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    assert retrieved.style_attributes == result.profile.style_attributes
    assert result.evidence.analyzer_version == "voice-dna-v1"


def test_analysis_rejects_profile_without_samples() -> None:
    services = _services(_memory_settings())

    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="Voice Workspace",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        name="Empty Voice",
    )

    with pytest.raises(
        ValueError,
        match="at least one non-empty",
    ):
        services.voice_profiles.analyze_profile(
            workspace_id=workspace.workspace_id,
            user_id=user.user_id,
            profile_id=profile.profile_id,
        )
