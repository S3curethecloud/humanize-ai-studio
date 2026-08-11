from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.models import RewriteRequest
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.models import VoiceSourceSample
from app.v2.repositories.sqlite import (
    initialize_database,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


class RecordingProvider:
    @property
    def provider_name(self) -> str:
        return "recording-provider"

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        return RewriteProviderResult(
            text=request.text,
            changes=[],
            provider_name=self.provider_name,
            model_name="recording-model",
            prompt_version="recording-v1",
            latency_ms=0.0,
            primary_provider_name=self.provider_name,
            fallback_used=False,
            provider_error_category=None,
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            ),
        )


def _services(
    *,
    backend: PersistenceBackend,
    sqlite_path: Path | None = None,
) -> V2Services:
    provider = VoiceAwareRewriteProvider(
        provider=RecordingProvider(),
    )

    workflow = RewriteWorkflow(
        provider=provider,
    )

    return V2Services(
        workflow=workflow,
        voice_aware_provider=provider,
        persistence_settings=V2PersistenceSettings(
            backend=backend,
            sqlite_path=sqlite_path,
            database_url=None,
        ),
    )


def _create_voice_rewrite(
    services: V2Services,
) -> tuple[str, str, str]:
    user = services.workspace.create_user(
        email="history-owner@example.com",
        display_name="History Owner",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="History Workspace",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        name="History Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id="history_sample_1",
                text=(
                    "I keep the message clear and practical. "
                    "I explain the important context carefully. "
                    "I document the result so the next action is obvious."
                ),
            ),
        ),
    )

    profile = services.voice_profiles.analyze_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        profile_id=profile.profile_id,
    ).profile

    assert profile.analysis_state.value == "current"
    assert services.voice_rewrite is not None

    result = services.voice_rewrite.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        profile_id=profile.profile_id,
        request=RewriteRequest(
            text=("Revenue was 42 million in 2025. The team completed the review."),
            document_type="general",
            audience="engineering leadership",
            tone="natural and clear",
            intensity="deep_reconstruction",
            preserve_numbers=True,
            preserve_dates=True,
        ),
    )

    assert result.history.voice_profile_id == profile.profile_id
    assert result.history.voice_guidance_version == "voice-rewrite-guidance-v1"
    assert result.history.voice_analysis_snapshot is not None
    assert result.history.voice_analysis_snapshot.analysis_state == "current"

    provenance = profile.analysis_provenance

    assert provenance is not None
    assert result.history.voice_analysis_snapshot.analyzer_version == provenance.analyzer_version
    assert result.history.voice_analysis_snapshot.analyzed_at == provenance.analyzed_at
    assert (
        result.history.voice_analysis_snapshot.source_fingerprint == provenance.source_fingerprint
    )
    assert result.history.voice_analysis_snapshot.sample_count == provenance.sample_count
    assert result.history.voice_analysis_snapshot.sufficiency == provenance.sufficiency.value
    assert result.history.voice_analysis_snapshot.consistency == provenance.consistency.value
    assert result.history.voice_analysis_snapshot.source_sample_ids == provenance.source_sample_ids
    assert result.history.voice_analysis_snapshot.style_attributes == profile.style_attributes

    return (
        user.user_id,
        workspace.workspace_id,
        profile.profile_id,
    )


def test_voice_evidence_is_persisted_in_memory_history() -> None:
    services = _services(
        backend=PersistenceBackend.MEMORY,
    )

    user_id, workspace_id, profile_id = _create_voice_rewrite(services)

    records = services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1
    assert records[0].voice_profile_id == profile_id
    assert records[0].voice_guidance_version == "voice-rewrite-guidance-v1"
    assert records[0].voice_analysis_snapshot is not None
    assert records[0].voice_analysis_snapshot.analysis_state == "current"
    assert records[0].voice_analysis_snapshot.analyzer_version == "voice-dna-v1"
    assert records[0].voice_analysis_snapshot.source_fingerprint
    assert records[0].voice_analysis_snapshot.source_sample_ids == ("history_sample_1",)
    assert records[0].voice_analysis_snapshot.style_attributes


def test_voice_evidence_survives_sqlite_service_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "voice-history.db"

    first_services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, profile_id = _create_voice_rewrite(first_services)

    second_services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    records = second_services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1
    assert records[0].voice_profile_id == profile_id
    assert records[0].voice_guidance_version == "voice-rewrite-guidance-v1"
    assert records[0].voice_analysis_snapshot is not None
    assert records[0].voice_analysis_snapshot.analysis_state == "current"
    assert records[0].voice_analysis_snapshot.analyzer_version == "voice-dna-v1"
    assert records[0].voice_analysis_snapshot.source_fingerprint
    assert records[0].voice_analysis_snapshot.source_sample_ids == ("history_sample_1",)
    assert records[0].voice_analysis_snapshot.style_attributes


def test_initialize_database_migrates_legacy_history_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-history.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE rewrite_history (
                rewrite_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                source_text TEXT NOT NULL,
                rewritten_text TEXT NOT NULL,
                document_type TEXT NOT NULL,
                audience TEXT NOT NULL,
                tone TEXT NOT NULL,
                intensity TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                fallback_used INTEGER NOT NULL,
                verification_decision TEXT NOT NULL,
                editorial_quality_decision TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(rewrite_history)").fetchall()
        }

    assert "voice_profile_id" in columns
    assert "voice_guidance_version" in columns
    assert "voice_analysis_snapshot" in columns


def test_rewrite_snapshot_survives_profile_reanalysis() -> None:
    services = _services(
        backend=PersistenceBackend.MEMORY,
    )

    user_id, workspace_id, profile_id = _create_voice_rewrite(services)

    before_records = services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(before_records) == 1

    original_snapshot = before_records[0].voice_analysis_snapshot

    assert original_snapshot is not None
    assert original_snapshot.source_sample_ids == ("history_sample_1",)

    original_style_attributes = original_snapshot.style_attributes

    profile = services.voice_profiles.get_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    )

    updated = services.voice_profiles.update_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile=profile.model_copy(
            update={
                "source_samples": (
                    VoiceSourceSample(
                        sample_id="history_sample_1",
                        text=(
                            "I changed this source after the rewrite. "
                            "The profile must become stale now. "
                            "A new analysis should produce new provenance."
                        ),
                    ),
                ),
            }
        ),
    )

    assert updated.analysis_state.value == "stale"

    reanalyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_id,
        user_id=user_id,
        profile_id=profile_id,
    ).profile

    assert reanalyzed.analysis_state.value == "current"
    assert reanalyzed.analysis_provenance is not None
    assert reanalyzed.analysis_provenance.source_fingerprint != original_snapshot.source_fingerprint

    after_records = services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(after_records) == 1
    assert after_records[0].voice_analysis_snapshot == original_snapshot
    assert after_records[0].voice_analysis_snapshot.style_attributes == original_style_attributes
    assert after_records[0].voice_analysis_snapshot.source_sample_ids == ("history_sample_1",)


@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    (
        (
            {
                "analysis_state": "stale",
            },
            "analysis_state",
        ),
        (
            {
                "source_fingerprint": "not-a-sha256",
            },
            "source_fingerprint",
        ),
        (
            {
                "sample_count": 0,
            },
            "sample_count",
        ),
        (
            {
                "sufficiency": "unknown",
            },
            "sufficiency",
        ),
        (
            {
                "consistency": "unknown",
            },
            "consistency",
        ),
    ),
)
def test_sqlite_history_rejects_corrupted_voice_snapshot(
    tmp_path: Path,
    mutation: dict[str, object],
    expected_fragment: str,
) -> None:
    database_path = tmp_path / "corrupted-history.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, _ = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                rewrite_id,
                voice_analysis_snapshot
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None
        assert row[1] is not None

        snapshot = json.loads(row[1])
        snapshot.update(mutation)

        connection.execute(
            """
            UPDATE rewrite_history
            SET voice_analysis_snapshot = ?
            WHERE rewrite_id = ?
            """,
            (
                json.dumps(snapshot),
                row[0],
            ),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValidationError,
        match=expected_fragment,
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


def test_sqlite_history_rejects_partial_voice_snapshot(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "partial-history.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, _ = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT rewrite_id
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None

        connection.execute(
            """
            UPDATE rewrite_history
            SET voice_analysis_snapshot = ?
            WHERE rewrite_id = ?
            """,
            (
                json.dumps(
                    {
                        "analysis_state": "current",
                        "analyzer_version": "voice-dna-v1",
                    }
                ),
                row[0],
            ),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(ValidationError):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


def test_sqlite_history_rejects_naive_analysis_timestamp(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "naive-timestamp-history.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, _ = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                rewrite_id,
                voice_analysis_snapshot
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None
        assert row[1] is not None

        snapshot = json.loads(row[1])
        snapshot["analyzed_at"] = "2026-08-11T12:00:00"

        connection.execute(
            """
            UPDATE rewrite_history
            SET voice_analysis_snapshot = ?
            WHERE rewrite_id = ?
            """,
            (
                json.dumps(snapshot),
                row[0],
            ),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


@pytest.mark.parametrize(
    "mutation_sql",
    (
        ("UPDATE rewrite_history SET voice_profile_id = NULL WHERE rewrite_id = ?"),
        ("UPDATE rewrite_history SET voice_guidance_version = NULL WHERE rewrite_id = ?"),
        ("UPDATE rewrite_history SET voice_analysis_snapshot = NULL WHERE rewrite_id = ?"),
    ),
)
def test_sqlite_history_rejects_partial_voice_audit_tuple(
    tmp_path: Path,
    mutation_sql: str,
) -> None:
    database_path = tmp_path / "partial-voice-audit.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, _ = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT rewrite_id
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None

        connection.execute(
            mutation_sql,
            (row[0],),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValidationError,
        match="voice audit fields must be all present or all absent",
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


@pytest.mark.parametrize(
    ("column_name", "expected_fragment"),
    (
        (
            "voice_profile_id",
            "voice_profile_id must be non-empty",
        ),
        (
            "voice_guidance_version",
            "voice_guidance_version must be non-empty",
        ),
    ),
)
def test_sqlite_history_rejects_blank_voice_audit_identifiers(
    tmp_path: Path,
    column_name: str,
    expected_fragment: str,
) -> None:
    database_path = tmp_path / "blank-voice-audit.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, _ = _create_voice_rewrite(services)

    statements = {
        "voice_profile_id": (
            "UPDATE rewrite_history SET voice_profile_id = '' WHERE rewrite_id = ?"
        ),
        "voice_guidance_version": (
            "UPDATE rewrite_history SET voice_guidance_version = '' WHERE rewrite_id = ?"
        ),
    }

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT rewrite_id
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None

        connection.execute(
            statements[column_name],
            (row[0],),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValidationError,
        match=expected_fragment,
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    (
        (
            {
                "sample_count": 2,
            },
            "sample_count must match source_sample_ids length",
        ),
        (
            {
                "source_sample_ids": [],
            },
            "sample_count must match source_sample_ids length",
        ),
        (
            {
                "source_sample_ids": [""],
            },
            "source_sample_ids must contain only non-empty identifiers",
        ),
        (
            {
                "source_sample_ids": ["   "],
            },
            "source_sample_ids must contain only non-empty identifiers",
        ),
    ),
)
def test_sqlite_history_rejects_incomplete_source_provenance(
    tmp_path: Path,
    mutation: dict[str, object],
    expected_fragment: str,
) -> None:
    database_path = tmp_path / "incomplete-source-provenance.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id, _ = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                rewrite_id,
                voice_analysis_snapshot
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None
        assert row[1] is not None

        snapshot = json.loads(row[1])
        snapshot.update(mutation)

        connection.execute(
            """
            UPDATE rewrite_history
            SET voice_analysis_snapshot = ?
            WHERE rewrite_id = ?
            """,
            (
                json.dumps(snapshot),
                row[0],
            ),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValidationError,
        match=expected_fragment,
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )
