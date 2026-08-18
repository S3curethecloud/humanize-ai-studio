from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_admin_audit import (
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
)
from app.v2.repositories.enterprise_quota_admin_mutations import (
    EnterpriseQuotaAdminMutationConfigurationError,
    InMemoryEnterpriseQuotaAdminMutationRepository,
    SQLiteEnterpriseQuotaAdminMutationRepository,
    build_enterprise_quota_admin_mutation_repository,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)

WORKSPACE_ID = "workspace_test"


def _quota_limit(
    *,
    quota_limit_id: str = "limit_requests",
) -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id=quota_limit_id,
        workspace_id=WORKSPACE_ID,
        dimension=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS
        ),
        window=EnterpriseQuotaWindow(
            window_start=datetime(
                2026,
                8,
                1,
                tzinfo=UTC,
            ),
            window_end=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
        ),
        limit=100,
    )


def _audit_event(
    *,
    audit_event_id: str = "audit_create",
    quota_limit_id: str = "limit_requests",
) -> EnterpriseAdminAuditEvent:
    return EnterpriseAdminAuditEvent(
        audit_event_id=audit_event_id,
        workspace_id=WORKSPACE_ID,
        actor_user_id="user_admin",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
        ),
        outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
        target_type="quota_limit",
        target_id=quota_limit_id,
        occurred_at=datetime(
            2026,
            8,
            15,
            20,
            0,
            tzinfo=UTC,
        ),
    )


def test_memory_success_commits_limit_and_audit() -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    quota_limit = _quota_limit()
    event = _audit_event()

    assert mutations.create_limit_with_audit(
        quota_limit=quota_limit,
        audit_event=event,
    ) == quota_limit

    assert (
        limits.get(quota_limit.quota_limit_id)
        == quota_limit
    )
    assert audit.get(event.audit_event_id) == event


def test_memory_duplicate_limit_commits_neither() -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    quota_limit = _quota_limit()
    limits.create(quota_limit)

    event = _audit_event()

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        mutations.create_limit_with_audit(
            quota_limit=quota_limit,
            audit_event=event,
        )

    assert audit.get(event.audit_event_id) is None


def test_memory_audit_collision_commits_no_limit() -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    event = _audit_event()
    audit.create(event)

    with pytest.raises(
        ValueError,
        match="audit event already exists",
    ):
        mutations.create_limit_with_audit(
            quota_limit=_quota_limit(),
            audit_event=event,
        )

    assert limits.get("limit_requests") is None


def test_memory_overlap_commits_no_success_audit() -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    limits.create(
        _quota_limit(
            quota_limit_id="existing",
        )
    )
    event = _audit_event(
        quota_limit_id="candidate",
    )

    with pytest.raises(
        ValueError,
        match="overlaps existing authority",
    ):
        mutations.create_limit_with_audit(
            quota_limit=_quota_limit(
                quota_limit_id="candidate",
            ),
            audit_event=event,
        )

    assert audit.get(event.audit_event_id) is None


def test_sqlite_success_commits_limit_and_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"
    limits = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    quota_limit = _quota_limit()
    event = _audit_event()

    assert mutations.create_limit_with_audit(
        quota_limit=quota_limit,
        audit_event=event,
    ) == quota_limit

    assert (
        limits.get(quota_limit.quota_limit_id)
        == quota_limit
    )
    assert audit.get(event.audit_event_id) == event


def test_sqlite_duplicate_limit_commits_neither(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"
    limits = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    quota_limit = _quota_limit()
    limits.create(quota_limit)
    event = _audit_event()

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        mutations.create_limit_with_audit(
            quota_limit=quota_limit,
            audit_event=event,
        )

    assert audit.get(event.audit_event_id) is None


def test_sqlite_audit_collision_rolls_back_limit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"
    limits = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    event = _audit_event()
    audit.create(event)

    with pytest.raises(
        ValueError,
        match="persistence integrity",
    ):
        mutations.create_limit_with_audit(
            quota_limit=_quota_limit(),
            audit_event=event,
        )

    assert limits.get("limit_requests") is None


def test_sqlite_overlap_commits_no_success_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"
    limits = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    limits.create(
        _quota_limit(
            quota_limit_id="existing",
        )
    )
    event = _audit_event(
        quota_limit_id="candidate",
    )

    with pytest.raises(
        ValueError,
        match="overlaps existing authority",
    ):
        mutations.create_limit_with_audit(
            quota_limit=_quota_limit(
                quota_limit_id="candidate",
            ),
            audit_event=event,
        )

    assert audit.get(event.audit_event_id) is None


def test_sqlite_mismatched_databases_fail_closed(
    tmp_path: Path,
) -> None:
    limits = SQLiteEnterpriseQuotaLimitRepository(
        database_path=tmp_path / "quota.db",
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=tmp_path / "audit.db",
    )

    with pytest.raises(
        EnterpriseQuotaAdminMutationConfigurationError,
        match="same SQLite database",
    ):
        SQLiteEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )


def test_factory_rejects_incompatible_backends(
    tmp_path: Path,
) -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=tmp_path / "audit.db",
    )

    with pytest.raises(
        EnterpriseQuotaAdminMutationConfigurationError,
        match="compatible",
    ):
        build_enterprise_quota_admin_mutation_repository(
            limits=limits,
            audit=audit,
        )


def test_atomic_contract_rejects_non_success_event() -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    event = EnterpriseAdminAuditEvent(
        audit_event_id="audit_failed",
        workspace_id=WORKSPACE_ID,
        actor_user_id="user_admin",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
        ),
        outcome=EnterpriseAdminAuditOutcome.FAILED,
        target_type="quota_limit",
        target_id="limit_requests",
        occurred_at=datetime(
            2026,
            8,
            15,
            20,
            0,
            tzinfo=UTC,
        ),
        failure_reason="test",
    )

    with pytest.raises(
        ValueError,
        match="SUCCEEDED",
    ):
        mutations.create_limit_with_audit(
            quota_limit=_quota_limit(),
            audit_event=event,
        )

    assert limits.get("limit_requests") is None
    assert audit.get("audit_failed") is None


def test_sqlite_failure_between_inserts_rolls_back_both(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v2.db"
    limits = SQLiteEnterpriseQuotaLimitRepository(
        database_path=database_path,
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    def fail_insert_event(
        *,
        connection: sqlite3.Connection,
        event: EnterpriseAdminAuditEvent,
    ) -> None:
        del connection
        del event
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr(
        "app.v2.repositories."
        "enterprise_quota_admin_mutations._insert_event",
        fail_insert_event,
    )

    with pytest.raises(
        RuntimeError,
        match="forced audit failure",
    ):
        mutations.create_limit_with_audit(
            quota_limit=_quota_limit(),
            audit_event=_audit_event(),
        )

    assert limits.get("limit_requests") is None
    assert audit.get("audit_create") is None
