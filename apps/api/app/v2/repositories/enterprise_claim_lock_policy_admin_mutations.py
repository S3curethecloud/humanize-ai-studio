from __future__ import annotations

import sqlite3
from typing import Protocol

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.repositories.enterprise_admin_audit import (
    EnterpriseAdminAuditRepository,
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
    _insert_event,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseClaimLockPolicyAlreadyExistsError,
    EnterpriseClaimLockPolicyIntegrityError,
    EnterpriseClaimLockPolicyNotFoundError,
    EnterpriseClaimLockPolicyRevisionConflictError,
    EnterpriseWorkspaceClaimLockPolicyRepository,
    InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
    _canonical_policy,
    _canonical_timestamp,
    _insert_policy,
    _memory_current_workspace_policy_exists,
    _policy_from_row,
    _require_creatable_policy,
    _sqlite_current_workspace_policy_exists,
    _sqlite_policy_id_exists,
    _validate_update_candidate,
)


class EnterpriseClaimLockPolicyAdminMutationRepository(
    Protocol
):
    def create_policy_with_audit(
        self,
        *,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceClaimLockPolicy: ...

    def update_policy_with_audit(
        self,
        *,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        expected_revision: int,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceClaimLockPolicy: ...


class EnterpriseClaimLockPolicyAdminMutationConfigurationError(
    RuntimeError
):
    pass


class InMemoryEnterpriseClaimLockPolicyAdminMutationRepository:
    def __init__(
        self,
        *,
        policies: InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
        audit: InMemoryEnterpriseAdminAuditRepository,
    ) -> None:
        self._policies = policies
        self._audit = audit

    def create_policy_with_audit(
        self,
        *,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        _require_success_create_audit(
            policy=policy,
            audit_event=audit_event,
        )
        _require_creatable_policy(policy)

        # Fixed lock order:
        # policy authority first, audit evidence second.
        with self._policies._lock, self._audit._lock:
            if policy.policy_id in self._policies._policies:
                raise EnterpriseClaimLockPolicyAlreadyExistsError(
                    "enterprise claim lock policy already exists: "
                    f"{policy.policy_id}"
                )

            if _memory_current_workspace_policy_exists(
                stored_policies=self._policies._policies,
                workspace_id=policy.workspace_id,
            ):
                raise EnterpriseClaimLockPolicyAlreadyExistsError(
                    "enterprise claim lock workspace already has "
                    "a non-archived policy"
                )

            if (
                audit_event.audit_event_id
                in self._audit._events
            ):
                raise ValueError(
                    "enterprise admin audit event already exists: "
                    f"{audit_event.audit_event_id}"
                )

            candidate_policies = dict(
                self._policies._policies
            )
            candidate_events = dict(
                self._audit._events
            )

            candidate_policies[
                policy.policy_id
            ] = policy
            candidate_events[
                audit_event.audit_event_id
            ] = audit_event

            self._policies._policies = candidate_policies
            self._audit._events = candidate_events

        return policy

    def update_policy_with_audit(
        self,
        *,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        expected_revision: int,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        _require_success_update_audit(
            policy=policy,
            audit_event=audit_event,
        )

        # Fixed lock order:
        # policy authority first, audit evidence second.
        with self._policies._lock, self._audit._lock:
            stored = self._policies._policies.get(
                policy.policy_id
            )

            if stored is None:
                raise EnterpriseClaimLockPolicyNotFoundError(
                    "enterprise claim lock policy not found: "
                    f"{policy.policy_id}"
                )

            _validate_update_candidate(
                stored=stored,
                candidate=policy,
                expected_revision=expected_revision,
            )

            if (
                audit_event.audit_event_id
                in self._audit._events
            ):
                raise ValueError(
                    "enterprise admin audit event already exists: "
                    f"{audit_event.audit_event_id}"
                )

            candidate_policies = dict(
                self._policies._policies
            )
            candidate_events = dict(
                self._audit._events
            )

            candidate_policies[
                policy.policy_id
            ] = policy
            candidate_events[
                audit_event.audit_event_id
            ] = audit_event

            self._policies._policies = candidate_policies
            self._audit._events = candidate_events

        return policy


class SQLiteEnterpriseClaimLockPolicyAdminMutationRepository:
    def __init__(
        self,
        *,
        policies: SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
        audit: SQLiteEnterpriseAdminAuditRepository,
    ) -> None:
        if policies._database_path != audit._database_path:
            raise (
                EnterpriseClaimLockPolicyAdminMutationConfigurationError(
                    "enterprise claim lock policy and admin audit "
                    "repositories must use the same SQLite database"
                )
            )

        self._database_path = policies._database_path

    def create_policy_with_audit(
        self,
        *,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        _require_success_create_audit(
            policy=policy,
            audit_event=audit_event,
        )
        _require_creatable_policy(policy)

        connection = sqlite3.connect(
            str(self._database_path)
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_policy_id_exists(
                connection=connection,
                policy_id=policy.policy_id,
            ):
                raise EnterpriseClaimLockPolicyAlreadyExistsError(
                    "enterprise claim lock policy already exists: "
                    f"{policy.policy_id}"
                )

            if _sqlite_current_workspace_policy_exists(
                connection=connection,
                workspace_id=policy.workspace_id,
            ):
                raise EnterpriseClaimLockPolicyAlreadyExistsError(
                    "enterprise claim lock workspace already has "
                    "a non-archived policy"
                )

            _insert_policy(
                connection=connection,
                policy=policy,
            )

            _insert_event(
                connection=connection,
                event=audit_event,
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise EnterpriseClaimLockPolicyIntegrityError(
                "enterprise claim lock policy admin atomic "
                "creation violated persistence integrity"
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return policy

    def update_policy_with_audit(
        self,
        *,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        expected_revision: int,
        audit_event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        _require_success_update_audit(
            policy=policy,
            audit_event=audit_event,
        )

        connection = sqlite3.connect(
            str(self._database_path)
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT *
                FROM enterprise_workspace_claim_lock_policies
                WHERE policy_id = ?
                """,
                (policy.policy_id,),
            ).fetchone()

            if row is None:
                raise EnterpriseClaimLockPolicyNotFoundError(
                    "enterprise claim lock policy not found: "
                    f"{policy.policy_id}"
                )

            stored = _policy_from_row(row)

            _validate_update_candidate(
                stored=stored,
                candidate=policy,
                expected_revision=expected_revision,
            )

            canonical = _canonical_policy(policy)

            cursor = connection.execute(
                """
                UPDATE enterprise_workspace_claim_lock_policies
                SET
                    workspace_id = ?,
                    policy_version = ?,
                    status = ?,
                    enforcement_mode = ?,
                    revision = ?,
                    created_by_user_id = ?,
                    created_at = ?,
                    updated_by_user_id = ?,
                    updated_at = ?,
                    payload = ?
                WHERE policy_id = ?
                  AND revision = ?
                """,
                (
                    canonical.workspace_id,
                    canonical.policy_version,
                    canonical.status.value,
                    canonical.enforcement_mode.value,
                    canonical.revision,
                    canonical.created_by_user_id,
                    _canonical_timestamp(
                        canonical.created_at
                    ),
                    canonical.updated_by_user_id,
                    _canonical_timestamp(
                        canonical.updated_at
                    ),
                    canonical.model_dump_json(),
                    canonical.policy_id,
                    expected_revision,
                ),
            )

            if cursor.rowcount != 1:
                raise EnterpriseClaimLockPolicyRevisionConflictError(
                    "enterprise claim lock policy revision conflict"
                )

            _insert_event(
                connection=connection,
                event=audit_event,
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise EnterpriseClaimLockPolicyIntegrityError(
                "enterprise claim lock policy admin atomic "
                "update violated persistence integrity"
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return policy


def build_enterprise_claim_lock_policy_admin_mutation_repository(
    *,
    policies: EnterpriseWorkspaceClaimLockPolicyRepository,
    audit: EnterpriseAdminAuditRepository,
) -> EnterpriseClaimLockPolicyAdminMutationRepository:
    if (
        isinstance(
            policies,
            InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
        )
        and isinstance(
            audit,
            InMemoryEnterpriseAdminAuditRepository,
        )
    ):
        return (
            InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
                policies=policies,
                audit=audit,
            )
        )

    if (
        isinstance(
            policies,
            SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
        )
        and isinstance(
            audit,
            SQLiteEnterpriseAdminAuditRepository,
        )
    ):
        return (
            SQLiteEnterpriseClaimLockPolicyAdminMutationRepository(
                policies=policies,
                audit=audit,
            )
        )

    raise EnterpriseClaimLockPolicyAdminMutationConfigurationError(
        "enterprise claim lock policy admin atomic mutation "
        "requires compatible policy and admin-audit repositories"
    )


def _require_success_create_audit(
    *,
    policy: EnterpriseWorkspaceClaimLockPolicy,
    audit_event: EnterpriseAdminAuditEvent,
) -> None:
    if (
        audit_event.action
        is not EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
    ):
        raise ValueError(
            "atomic claim lock policy creation requires "
            "CLAIM_LOCK_POLICY_CREATE audit action"
        )

    _require_success_policy_audit(
        policy=policy,
        audit_event=audit_event,
    )


def _require_success_update_audit(
    *,
    policy: EnterpriseWorkspaceClaimLockPolicy,
    audit_event: EnterpriseAdminAuditEvent,
) -> None:
    allowed_actions = {
        EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE,
        EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ENABLE,
        EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_DISABLE,
        EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ARCHIVE,
    }

    if audit_event.action not in allowed_actions:
        raise ValueError(
            "atomic claim lock policy update requires "
            "UPDATE, ENABLE, DISABLE, or ARCHIVE audit action"
        )

    _require_success_policy_audit(
        policy=policy,
        audit_event=audit_event,
    )


def _require_success_policy_audit(
    *,
    policy: EnterpriseWorkspaceClaimLockPolicy,
    audit_event: EnterpriseAdminAuditEvent,
) -> None:
    if (
        audit_event.outcome
        is not EnterpriseAdminAuditOutcome.SUCCEEDED
    ):
        raise ValueError(
            "atomic claim lock policy mutation requires "
            "SUCCEEDED audit outcome"
        )

    if audit_event.workspace_id != policy.workspace_id:
        raise ValueError(
            "atomic claim lock policy audit workspace "
            "must match policy workspace"
        )

    if audit_event.target_type != "claim_lock_policy":
        raise ValueError(
            "atomic claim lock policy audit target_type "
            "must be claim_lock_policy"
        )

    if audit_event.target_id != policy.policy_id:
        raise ValueError(
            "atomic claim lock policy audit target_id "
            "must match policy"
        )
