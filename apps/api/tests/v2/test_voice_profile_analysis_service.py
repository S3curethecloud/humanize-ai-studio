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

    workspace = services.workspace_provisioning.create_workspace(
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
    assert result.evidence.sufficiency.value == "insufficient"

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
        match="membership_not_found",
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
    assert result.evidence.sufficiency.value == "insufficient"

    assert retrieved.analysis_state.value == "current"
    assert retrieved.analysis_provenance is not None
    assert retrieved.analysis_provenance == result.profile.analysis_provenance
    assert retrieved.analysis_provenance.source_sample_ids == ("sample_1",)
    assert (
        retrieved.analysis_provenance.source_fingerprint
        == result.profile.analysis_provenance.source_fingerprint
    )


def test_analysis_rejects_profile_without_samples() -> None:
    services = _services(_memory_settings())

    user = services.workspace.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
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


def test_analysis_persists_current_provenance_in_memory() -> None:
    services = _services(_memory_settings())

    user_id, workspace_id, profile_id = _create_profile(services)

    before = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    assert before.analysis_state.value == "never_analyzed"
    assert before.analysis_provenance is None

    result = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    provenance = result.profile.analysis_provenance

    assert result.profile.analysis_state.value == "current"
    assert provenance is not None
    assert provenance.analyzer_version == "voice-dna-v1"
    assert provenance.source_sample_ids == ("sample_1",)
    assert provenance.sample_count == 1
    assert provenance.sufficiency == result.evidence.sufficiency
    assert provenance.consistency == result.evidence.sample_consistency.classification
    assert len(provenance.source_fingerprint) == 64
    assert provenance.analyzed_at == result.profile.updated_at

    retrieved = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    assert retrieved.analysis_state.value == "current"
    assert retrieved.analysis_provenance == provenance


def test_profile_metadata_update_preserves_current_analysis() -> None:
    services = _services(_memory_settings())

    user_id, workspace_id, profile_id = _create_profile(services)

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    ).profile

    updated = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=analyzed.model_copy(
            update={
                "name": "Renamed Voice",
                "description": "Metadata-only change.",
            }
        ),
    )

    assert updated.analysis_state.value == "current"
    assert updated.analysis_provenance == analyzed.analysis_provenance


def test_source_sample_change_marks_analysis_stale() -> None:
    services = _services(_memory_settings())

    user_id, workspace_id, profile_id = _create_profile(services)

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    ).profile

    prior_provenance = analyzed.analysis_provenance

    changed_samples = (
        VoiceSourceSample(
            sample_id="sample_1",
            text=(
                "Ship the update tomorrow. "
                "Review the evidence carefully. "
                "Document the final result."
            ),
        ),
    )

    updated = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=analyzed.model_copy(
            update={
                "source_samples": changed_samples,
            }
        ),
    )

    assert updated.analysis_state.value == "stale"
    assert updated.analysis_provenance == prior_provenance


def test_manual_style_change_marks_analysis_stale() -> None:
    services = _services(_memory_settings())

    user_id, workspace_id, profile_id = _create_profile(services)

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    ).profile

    changed_style = analyzed.style_attributes.model_copy(
        update={
            "directness": VoiceDirectness.INDIRECT,
        }
    )

    updated = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=analyzed.model_copy(
            update={
                "style_attributes": changed_style,
            }
        ),
    )

    assert updated.analysis_state.value == "stale"
    assert updated.analysis_provenance == analyzed.analysis_provenance


def test_stale_analysis_remains_stale_until_reanalysis() -> None:
    services = _services(_memory_settings())

    user_id, workspace_id, profile_id = _create_profile(services)

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    ).profile

    changed = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=analyzed.model_copy(
            update={
                "source_samples": (
                    VoiceSourceSample(
                        sample_id="sample_1",
                        text="A changed writing sample.",
                    ),
                ),
            }
        ),
    )

    assert changed.analysis_state.value == "stale"

    reverted = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=changed.model_copy(
            update={
                "source_samples": analyzed.source_samples,
            }
        ),
    )

    assert reverted.analysis_state.value == "stale"

    reanalyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    ).profile

    assert reanalyzed.analysis_state.value == "current"
    assert reanalyzed.analysis_provenance is not None
    analyzed_provenance = analyzed.analysis_provenance
    reanalyzed_provenance = reanalyzed.analysis_provenance

    assert analyzed_provenance is not None
    assert reanalyzed_provenance is not None

    assert reanalyzed_provenance.analyzed_at >= analyzed_provenance.analyzed_at
