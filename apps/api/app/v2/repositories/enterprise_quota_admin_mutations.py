from __future__ import annotations

import sqlite3
from typing import Protocol

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_admin_audit import (
    EnterpriseAdminAuditRepository,
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
    _insert_event,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
    _insert_limit,
    _require_no_memory_overlap,
    _sqlite_limit_id_exists,
    _sqlite_overlap_exists,
)


class EnterpriseQuotaAdminMutationRepository(Protocol):
    def create_limit_with_audit(
        self,
        *,
        quota_limit: EnterpriseWorkspaceQuotaLimit,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceQuotaLimit: ...


class EnterpriseQuotaAdminMutationConfigurationError(
    RuntimeError
):
    pass


class InMemoryEnterpriseQuotaAdminMutationRepository:
    def __init__(
        self,
        *,
        limits: InMemoryEnterpriseQuotaLimitRepository,
        audit: InMemoryEnterpriseAdminAuditRepository,
    ) -> None:
        self._limits = limits
        self._audit = audit

    def create_limit_with_audit(
        self,
        *,
        quota_limit: EnterpriseWorkspaceQuotaLimit,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceQuotaLimit:
        _require_success_create_audit(
            quota_limit=quota_limit,
            audit_event=audit_event,
        )

        # Fixed lock order is part of the repository contract:
        # quota authority first, audit evidence second.
        with self._limits._lock, self._audit._lock:
            if (
                quota_limit.quota_limit_id
                in self._limits._limits
            ):
                raise ValueError(
                    "enterprise quota limit already exists: "
                    f"{quota_limit.quota_limit_id}"
                )

            _require_no_memory_overlap(
                stored_limits=self._limits._limits,
                candidate=quota_limit,
            )

            if (
                audit_event.audit_event_id
                in self._audit._events
            ):
                raise ValueError(
                    "enterprise admin audit event "
                    "already exists: "
                    f"{audit_event.audit_event_id}"
                )

            candidate_limits = dict(
                self._limits._limits
            )
            candidate_events = dict(
                self._audit._events
            )

            candidate_limits[
                quota_limit.quota_limit_id
            ] = quota_limit
            candidate_events[
                audit_event.audit_event_id
            ] = audit_event

            # Both locks remain held until both authoritative
            # state references have been replaced, so readers
            # cannot observe a partial successful mutation.
            self._limits._limits = candidate_limits
            self._audit._events = candidate_events

        return quota_limit


class SQLiteEnterpriseQuotaAdminMutationRepository:
    def __init__(
        self,
        *,
        limits: SQLiteEnterpriseQuotaLimitRepository,
        audit: SQLiteEnterpriseAdminAuditRepository,
    ) -> None:
        if limits._database_path != audit._database_path:
            raise EnterpriseQuotaAdminMutationConfigurationError(
                "enterprise quota limit and admin audit "
                "repositories must use the same SQLite database"
            )

        self._database_path = limits._database_path

    def create_limit_with_audit(
        self,
        *,
        quota_limit: EnterpriseWorkspaceQuotaLimit,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceQuotaLimit:
        _require_success_create_audit(
            quota_limit=quota_limit,
            audit_event=audit_event,
        )

        connection = sqlite3.connect(
            str(self._database_path)
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_limit_id_exists(
                connection=connection,
                quota_limit_id=(
                    quota_limit.quota_limit_id
                ),
            ):
                raise ValueError(
                    "enterprise quota limit already exists: "
                    f"{quota_limit.quota_limit_id}"
                )

            if _sqlite_overlap_exists(
                connection=connection,
                candidate=quota_limit,
            ):
                raise ValueError(
                    "enterprise quota limit overlaps "
                    "existing authority"
                )

            _insert_limit(
                connection=connection,
                limit=quota_limit,
            )

            _insert_event(
                connection=connection,
                event=audit_event,
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ValueError(
                "enterprise quota admin atomic mutation "
                "violated persistence integrity"
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return quota_limit


def build_enterprise_quota_admin_mutation_repository(
    *,
    limits: EnterpriseQuotaLimitRepository,
    audit: EnterpriseAdminAuditRepository,
) -> EnterpriseQuotaAdminMutationRepository:
    if (
        isinstance(
            limits,
            InMemoryEnterpriseQuotaLimitRepository,
        )
        and isinstance(
            audit,
            InMemoryEnterpriseAdminAuditRepository,
        )
    ):
        return (
            InMemoryEnterpriseQuotaAdminMutationRepository(
                limits=limits,
                audit=audit,
            )
        )

    if (
        isinstance(
            limits,
            SQLiteEnterpriseQuotaLimitRepository,
        )
        and isinstance(
            audit,
            SQLiteEnterpriseAdminAuditRepository,
        )
    ):
        return (
            SQLiteEnterpriseQuotaAdminMutationRepository(
                limits=limits,
                audit=audit,
            )
        )

    raise EnterpriseQuotaAdminMutationConfigurationError(
        "enterprise quota admin atomic mutation requires "
        "compatible quota-limit and admin-audit repositories"
    )


def _require_success_create_audit(
    *,
    quota_limit: EnterpriseWorkspaceQuotaLimit,
    audit_event: EnterpriseAdminAuditEvent,
) -> None:
    if (
        audit_event.action
        is not EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
    ):
        raise ValueError(
            "atomic quota creation requires "
            "QUOTA_LIMIT_CREATE audit action"
        )

    if (
        audit_event.outcome
        is not EnterpriseAdminAuditOutcome.SUCCEEDED
    ):
        raise ValueError(
            "atomic quota creation requires "
            "SUCCEEDED audit outcome"
        )

    if audit_event.workspace_id != quota_limit.workspace_id:
        raise ValueError(
            "atomic quota creation audit workspace "
            "must match quota limit workspace"
        )

    if audit_event.target_type != "quota_limit":
        raise ValueError(
            "atomic quota creation audit target_type "
            "must be quota_limit"
        )

    if (
        audit_event.target_id
        != quota_limit.quota_limit_id
    ):
        raise ValueError(
            "atomic quota creation audit target_id "
            "must match quota limit"
        )
