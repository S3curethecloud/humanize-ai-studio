from __future__ import annotations

from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditOutcome,
)
from app.v2.repositories.enterprise_admin_audit import (
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordInput,
)
from app.v2.services.enterprise_admin_audit_runtime_factory import (
    ExternalEnterpriseAdminAuditPersistenceUnavailableError,
    build_enterprise_admin_audit_runtime,
)


def _command() -> EnterpriseAdminAuditRecordInput:
    return EnterpriseAdminAuditRecordInput(
        workspace_id="workspace_1",
        actor_user_id="user_admin",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_LIST
        ),
        outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
    )


def test_memory_runtime_exposes_repository_and_recorder() -> None:
    runtime = build_enterprise_admin_audit_runtime(
        V2PersistenceSettings(
            backend=PersistenceBackend.MEMORY,
            sqlite_path=None,
            database_url=None,
        )
    )

    assert isinstance(
        runtime.repository,
        InMemoryEnterpriseAdminAuditRepository,
    )

    event = runtime.recording.record(_command())

    assert runtime.repository.get(
        event.audit_event_id
    ) == event


def test_sqlite_runtime_uses_configured_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    first = build_enterprise_admin_audit_runtime(
        settings
    )

    assert isinstance(
        first.repository,
        SQLiteEnterpriseAdminAuditRepository,
    )

    event = first.recording.record(_command())

    second = build_enterprise_admin_audit_runtime(
        settings
    )

    assert second.repository.get(
        event.audit_event_id
    ) == event


def test_external_runtime_fails_explicitly() -> None:
    with pytest.raises(
        ExternalEnterpriseAdminAuditPersistenceUnavailableError,
        match="no adapter has been installed",
    ):
        build_enterprise_admin_audit_runtime(
            V2PersistenceSettings(
                backend=PersistenceBackend.EXTERNAL,
                sqlite_path=None,
                database_url=(
                    "postgresql://example.invalid/v2"
                ),
            )
        )


def test_sqlite_settings_are_validated() -> None:
    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_SQLITE_PATH",
    ):
        build_enterprise_admin_audit_runtime(
            V2PersistenceSettings(
                backend=PersistenceBackend.SQLITE,
                sqlite_path=None,
                database_url=None,
            )
        )
