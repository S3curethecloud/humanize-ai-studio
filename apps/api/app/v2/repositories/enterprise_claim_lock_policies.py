from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)


class EnterpriseClaimLockPolicyAlreadyExistsError(ValueError):
    pass


class EnterpriseClaimLockPolicyRevisionConflictError(ValueError):
    pass


class EnterpriseClaimLockPolicyIntegrityError(RuntimeError):
    pass


class EnterpriseClaimLockPolicyNotFoundError(LookupError):
    pass


class EnterpriseClaimLockPolicyArchivedError(ValueError):
    pass


class EnterpriseWorkspaceClaimLockPolicyRepository(Protocol):
    def create(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
    ) -> EnterpriseWorkspaceClaimLockPolicy: ...

    def get_by_id(
        self,
        policy_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None: ...

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None: ...

    def update(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy: ...


class InMemoryEnterpriseWorkspaceClaimLockPolicyRepository:
    def __init__(self) -> None:
        self._policies: dict[
            str,
            EnterpriseWorkspaceClaimLockPolicy,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        _require_creatable_policy(policy)

        with self._lock:
            if policy.policy_id in self._policies:
                raise EnterpriseClaimLockPolicyAlreadyExistsError(
                    "enterprise claim lock policy already exists: "
                    f"{policy.policy_id}"
                )

            if _memory_current_workspace_policy_exists(
                stored_policies=self._policies,
                workspace_id=policy.workspace_id,
            ):
                raise EnterpriseClaimLockPolicyAlreadyExistsError(
                    "enterprise claim lock workspace already has "
                    "a non-archived policy"
                )

            candidate_policies = dict(self._policies)
            candidate_policies[policy.policy_id] = policy
            self._policies = candidate_policies

        return policy

    def get_by_id(
        self,
        policy_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        with self._lock:
            return self._policies.get(policy_id)

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        with self._lock:
            matches = tuple(
                policy
                for policy in self._policies.values()
                if (
                    policy.workspace_id == workspace_id
                    and policy.status
                    is not EnterpriseClaimLockPolicyStatus.ARCHIVED
                )
            )

        return _require_unambiguous_workspace_policy(matches)

    def update(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        with self._lock:
            stored = self._policies.get(policy.policy_id)

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

            candidate_policies = dict(self._policies)
            candidate_policies[policy.policy_id] = policy
            self._policies = candidate_policies

        return policy


class SQLiteEnterpriseWorkspaceClaimLockPolicyRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        _require_creatable_policy(policy)

        connection = self._connect()

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

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise EnterpriseClaimLockPolicyAlreadyExistsError(
                "enterprise claim lock policy creation "
                "violated persistence uniqueness"
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return policy

    def get_by_id(
        self,
        policy_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM enterprise_workspace_claim_lock_policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            ).fetchone()

        if row is None:
            return None

        return _policy_from_row(row)

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM enterprise_workspace_claim_lock_policies
                WHERE workspace_id = ?
                  AND status != 'archived'
                ORDER BY policy_id ASC
                LIMIT 2
                """,
                (workspace_id,),
            ).fetchall()

        matches = tuple(
            _policy_from_row(row)
            for row in rows
        )

        return _require_unambiguous_workspace_policy(matches)

    def update(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        connection = self._connect()

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
                    _canonical_timestamp(canonical.created_at),
                    canonical.updated_by_user_id,
                    _canonical_timestamp(canonical.updated_at),
                    canonical.model_dump_json(),
                    canonical.policy_id,
                    expected_revision,
                ),
            )

            if cursor.rowcount != 1:
                raise EnterpriseClaimLockPolicyRevisionConflictError(
                    "enterprise claim lock policy revision conflict"
                )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise EnterpriseClaimLockPolicyIntegrityError(
                "enterprise claim lock policy update "
                "violated persistence integrity"
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return policy

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    enterprise_workspace_claim_lock_policies (
                        policy_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        policy_version TEXT NOT NULL,
                        status TEXT NOT NULL,
                        enforcement_mode TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_by_user_id TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_enterprise_claim_lock_policy_current_workspace
                ON enterprise_workspace_claim_lock_policies (
                    workspace_id
                )
                WHERE status != 'archived';

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_claim_lock_policy_workspace
                ON enterprise_workspace_claim_lock_policies (
                    workspace_id,
                    status,
                    policy_id
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row

        return connection


def _require_creatable_policy(
    policy: EnterpriseWorkspaceClaimLockPolicy,
) -> None:
    if policy.revision != 1:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock policy must be created at revision 1"
        )

    if policy.status is EnterpriseClaimLockPolicyStatus.ARCHIVED:
        raise EnterpriseClaimLockPolicyArchivedError(
            "enterprise claim lock policy cannot be created archived"
        )


def _validate_update_candidate(
    *,
    stored: EnterpriseWorkspaceClaimLockPolicy,
    candidate: EnterpriseWorkspaceClaimLockPolicy,
    expected_revision: int,
) -> None:
    if stored.status is EnterpriseClaimLockPolicyStatus.ARCHIVED:
        raise EnterpriseClaimLockPolicyArchivedError(
            "enterprise claim lock policy is archived "
            "and cannot be updated"
        )

    if stored.revision != expected_revision:
        raise EnterpriseClaimLockPolicyRevisionConflictError(
            "enterprise claim lock policy revision conflict: "
            f"expected {expected_revision}, stored {stored.revision}"
        )

    if candidate.revision != expected_revision + 1:
        raise EnterpriseClaimLockPolicyRevisionConflictError(
            "enterprise claim lock policy candidate revision "
            "must equal expected revision plus one"
        )

    if candidate.policy_id != stored.policy_id:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock policy_id is immutable"
        )

    if candidate.workspace_id != stored.workspace_id:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock workspace_id is immutable"
        )

    if candidate.policy_version != stored.policy_version:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock policy_version is immutable"
        )

    if candidate.created_by_user_id != stored.created_by_user_id:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock created_by_user_id is immutable"
        )

    if candidate.created_at != stored.created_at:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock created_at is immutable"
        )

    _require_allowed_status_change(
        current=stored.status,
        requested=candidate.status,
    )


def _require_allowed_status_change(
    *,
    current: EnterpriseClaimLockPolicyStatus,
    requested: EnterpriseClaimLockPolicyStatus,
) -> None:
    if requested is current:
        return

    allowed: dict[
        EnterpriseClaimLockPolicyStatus,
        frozenset[EnterpriseClaimLockPolicyStatus],
    ] = {
        EnterpriseClaimLockPolicyStatus.ACTIVE: frozenset(
            {
                EnterpriseClaimLockPolicyStatus.DISABLED,
                EnterpriseClaimLockPolicyStatus.ARCHIVED,
            }
        ),
        EnterpriseClaimLockPolicyStatus.DISABLED: frozenset(
            {
                EnterpriseClaimLockPolicyStatus.ACTIVE,
                EnterpriseClaimLockPolicyStatus.ARCHIVED,
            }
        ),
        EnterpriseClaimLockPolicyStatus.ARCHIVED: frozenset(),
    }

    if requested not in allowed[current]:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock policy lifecycle "
            f"transition is not allowed: "
            f"{current.value} -> {requested.value}"
        )


def _memory_current_workspace_policy_exists(
    *,
    stored_policies: dict[
        str,
        EnterpriseWorkspaceClaimLockPolicy,
    ],
    workspace_id: str,
) -> bool:
    return any(
        policy.workspace_id == workspace_id
        and policy.status
        is not EnterpriseClaimLockPolicyStatus.ARCHIVED
        for policy in stored_policies.values()
    )


def _sqlite_policy_id_exists(
    *,
    connection: sqlite3.Connection,
    policy_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM enterprise_workspace_claim_lock_policies
        WHERE policy_id = ?
        LIMIT 1
        """,
        (policy_id,),
    ).fetchone()

    return row is not None


def _sqlite_current_workspace_policy_exists(
    *,
    connection: sqlite3.Connection,
    workspace_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM enterprise_workspace_claim_lock_policies
        WHERE workspace_id = ?
          AND status != 'archived'
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()

    return row is not None


def _insert_policy(
    *,
    connection: sqlite3.Connection,
    policy: EnterpriseWorkspaceClaimLockPolicy,
) -> None:
    canonical = _canonical_policy(policy)

    connection.execute(
        """
        INSERT INTO enterprise_workspace_claim_lock_policies (
            policy_id,
            workspace_id,
            policy_version,
            status,
            enforcement_mode,
            revision,
            created_by_user_id,
            created_at,
            updated_by_user_id,
            updated_at,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            canonical.policy_id,
            canonical.workspace_id,
            canonical.policy_version,
            canonical.status.value,
            canonical.enforcement_mode.value,
            canonical.revision,
            canonical.created_by_user_id,
            _canonical_timestamp(canonical.created_at),
            canonical.updated_by_user_id,
            _canonical_timestamp(canonical.updated_at),
            canonical.model_dump_json(),
        ),
    )


def _policy_from_row(
    row: sqlite3.Row,
) -> EnterpriseWorkspaceClaimLockPolicy:
    policy = (
        EnterpriseWorkspaceClaimLockPolicy.model_validate_json(
            row["payload"]
        )
    )

    expected = {
        "policy_id": policy.policy_id,
        "workspace_id": policy.workspace_id,
        "policy_version": policy.policy_version,
        "status": policy.status.value,
        "enforcement_mode": policy.enforcement_mode.value,
        "revision": policy.revision,
        "created_by_user_id": policy.created_by_user_id,
        "created_at": _canonical_timestamp(policy.created_at),
        "updated_by_user_id": policy.updated_by_user_id,
        "updated_at": _canonical_timestamp(policy.updated_at),
    }

    for column, expected_value in expected.items():
        if row[column] != expected_value:
            raise EnterpriseClaimLockPolicyIntegrityError(
                "enterprise claim lock policy persistence "
                f"integrity mismatch for {column}"
            )

    return policy


def _require_unambiguous_workspace_policy(
    matches: tuple[
        EnterpriseWorkspaceClaimLockPolicy,
        ...,
    ],
) -> EnterpriseWorkspaceClaimLockPolicy | None:
    if not matches:
        return None

    if len(matches) != 1:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock workspace policy "
            "resolution is ambiguous"
        )

    return matches[0]


def _canonical_policy(
    policy: EnterpriseWorkspaceClaimLockPolicy,
) -> EnterpriseWorkspaceClaimLockPolicy:
    return policy.model_copy(
        update={
            "created_at": _canonical_datetime(policy.created_at),
            "updated_at": _canonical_datetime(policy.updated_at),
        }
    )


def _canonical_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EnterpriseClaimLockPolicyIntegrityError(
            "enterprise claim lock policy repository "
            "timestamps must be timezone-aware"
        )

    return value.astimezone(UTC)


def _canonical_timestamp(
    value: datetime,
) -> str:
    return _canonical_datetime(value).isoformat()
