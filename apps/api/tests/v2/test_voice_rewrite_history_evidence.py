from __future__ import annotations

import sqlite3
from pathlib import Path

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
    )

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

    assert result.history.voice_profile_id == (profile.profile_id)
    assert result.history.voice_guidance_version == "voice-rewrite-guidance-v1"

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
