from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.v2.api.dependencies import V2Services
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
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
    EnterpriseAdminAuditRecordInput,
)
from app.v2.services.enterprise_admin_audit_runtime import (
    EnterpriseAdminAuditRuntime,
)


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _command() -> EnterpriseAdminAuditRecordInput:
    return EnterpriseAdminAuditRecordInput(
        workspace_id="workspace_1",
        actor_user_id="user_admin",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_GET
        ),
        outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
        target_type="quota_limit",
        target_id="limit_requests",
    )


def test_explicit_runtime_is_preserved_exactly() -> None:
    repository = (
        InMemoryEnterpriseAdminAuditRepository()
    )
    runtime = EnterpriseAdminAuditRuntime(
        repository=repository,
        recording=EnterpriseAdminAuditRecordingService(
            repository=repository,
        ),
    )

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
        enterprise_admin_audit_runtime=runtime,
    )

    assert services.enterprise_admin_audit is runtime


def test_default_memory_composition_is_operational() -> None:
    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
    )

    event = (
        services.enterprise_admin_audit.recording.record(
            _command()
        )
    )

    assert (
        services.enterprise_admin_audit.repository.get(
            event.audit_event_id
        )
        == event
    )


def test_sqlite_composition_uses_v2_database_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    first = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
    )

    event = (
        first.enterprise_admin_audit.recording.record(
            _command()
        )
    )

    second = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
    )

    assert (
        second.enterprise_admin_audit.repository.get(
            event.audit_event_id
        )
        == event
    )
