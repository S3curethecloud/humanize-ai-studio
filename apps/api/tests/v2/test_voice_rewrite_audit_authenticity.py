from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

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
from app.v2.config.voice_audit_auth import (
    VoiceAuditAuthenticitySettings,
)
from app.v2.domain.models import (
    VoiceRewriteAnalysisBinding,
    VoiceRewriteAnalysisSnapshot,
    VoiceSourceSample,
)
from app.v2.services.voice_audit_authenticator import (
    VoiceAuditHmacKey,
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


def _auth_settings(
    *,
    active_key_id: str = "voice-audit-key-v1",
    keys: tuple[VoiceAuditHmacKey, ...] | None = None,
) -> VoiceAuditAuthenticitySettings:
    resolved_keys = keys or (
        VoiceAuditHmacKey(
            key_id="voice-audit-key-v1",
            secret=b"a" * 32,
        ),
    )

    return VoiceAuditAuthenticitySettings(
        enabled=True,
        active_key_id=active_key_id,
        keys=resolved_keys,
    )


def _services(
    *,
    backend: PersistenceBackend,
    sqlite_path: Path | None = None,
    auth_settings: VoiceAuditAuthenticitySettings | None = None,
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
        voice_audit_auth_settings=(auth_settings or _auth_settings()),
    )


def _create_voice_rewrite(
    services: V2Services,
) -> tuple[str, str]:
    user = services.workspace.create_user(
        email="auth-history-owner@example.com",
        display_name="Auth History Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=user.user_id,
        name="Authenticated History Workspace",
    )

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        name="Authenticated History Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id="auth_history_sample_1",
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

    assert result.history.voice_analysis_snapshot is not None
    assert result.history.voice_analysis_binding is not None
    assert result.history.voice_analysis_authenticity is not None

    return (
        user.user_id,
        workspace.workspace_id,
    )


def test_authenticated_voice_history_is_valid_in_memory() -> None:
    services = _services(
        backend=PersistenceBackend.MEMORY,
    )

    user_id, workspace_id = _create_voice_rewrite(services)

    records = services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1

    record = records[0]

    assert record.voice_analysis_snapshot is not None
    assert record.voice_analysis_binding is not None
    assert record.voice_analysis_authenticity is not None
    assert record.voice_analysis_authenticity.algorithm == "hmac-sha256"
    assert (
        record.voice_analysis_authenticity.authentication_version
        == "voice-snapshot-authenticity-v1"
    )
    assert record.voice_analysis_authenticity.key_id == "voice-audit-key-v1"


def test_authenticated_voice_history_survives_sqlite_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "authenticated-history.db"

    first_services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id = _create_voice_rewrite(first_services)

    second_services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    records = second_services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1
    assert records[0].voice_analysis_authenticity is not None
    assert records[0].voice_analysis_authenticity.key_id == "voice-audit-key-v1"


def test_authenticated_history_accepts_retained_rotated_key(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "rotated-auth-history.db"

    first_services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        auth_settings=_auth_settings(),
    )

    user_id, workspace_id = _create_voice_rewrite(first_services)

    rotated_settings = _auth_settings(
        active_key_id="voice-audit-key-v2",
        keys=(
            VoiceAuditHmacKey(
                key_id="voice-audit-key-v1",
                secret=b"a" * 32,
            ),
            VoiceAuditHmacKey(
                key_id="voice-audit-key-v2",
                secret=b"b" * 32,
            ),
        ),
    )

    second_services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        auth_settings=rotated_settings,
    )

    records = second_services.history.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1
    assert records[0].voice_analysis_authenticity is not None
    assert records[0].voice_analysis_authenticity.key_id == "voice-audit-key-v1"


def test_authenticated_history_rejects_missing_hmac(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "missing-auth-history.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE rewrite_history
            SET voice_analysis_authenticity = NULL
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValueError,
        match="voice analysis authenticity is required",
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


def test_authenticated_history_rejects_modified_hmac(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "modified-auth-history.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                rewrite_id,
                voice_analysis_authenticity
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None
        assert row[1] is not None

        authenticity = json.loads(row[1])
        authenticity["mac"] = "b" * 64

        connection.execute(
            """
            UPDATE rewrite_history
            SET voice_analysis_authenticity = ?
            WHERE rewrite_id = ?
            """,
            (
                json.dumps(
                    authenticity,
                    separators=(",", ":"),
                ),
                row[0],
            ),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValueError,
        match="voice analysis authenticity verification failed",
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )


def test_attacker_cannot_bypass_hmac_by_recomputing_public_binding(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "recomputed-public-binding.db"

    services = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    user_id, workspace_id = _create_voice_rewrite(services)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                rewrite_id,
                voice_analysis_snapshot,
                voice_analysis_binding,
                voice_analysis_authenticity
            FROM rewrite_history
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert row is not None
        assert row[1] is not None
        assert row[2] is not None
        assert row[3] is not None

        snapshot_payload = json.loads(row[1])

        original_fingerprint = snapshot_payload["source_fingerprint"]

        snapshot_payload["source_fingerprint"] = (
            "b" * 64 if original_fingerprint != "b" * 64 else "c" * 64
        )

        tampered_snapshot = VoiceRewriteAnalysisSnapshot.model_validate(snapshot_payload)

        recomputed_binding = VoiceRewriteAnalysisBinding.from_snapshot(tampered_snapshot)

        connection.execute(
            """
            UPDATE rewrite_history
            SET
                voice_analysis_snapshot = ?,
                voice_analysis_binding = ?
            WHERE rewrite_id = ?
            """,
            (
                json.dumps(
                    tampered_snapshot.model_dump(mode="json"),
                    separators=(",", ":"),
                ),
                json.dumps(
                    recomputed_binding.model_dump(mode="json"),
                    separators=(",", ":"),
                ),
                row[0],
            ),
        )

    restarted = _services(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
    )

    with pytest.raises(
        ValueError,
        match="voice analysis authenticity verification failed",
    ):
        restarted.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )
