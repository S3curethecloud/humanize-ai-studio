from __future__ import annotations

import sqlite3
from pathlib import Path

from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.repositories.enterprise_provider_routing_policies import (
    EnterpriseProviderRoutingPolicyAlreadyExistsError,
    EnterpriseProviderRoutingPolicyIntegrityError,
    EnterpriseProviderRoutingPolicyNotFoundError,
    EnterpriseProviderRoutingPolicyRevisionConflictError,
    _require_creatable_policy,
    _require_unambiguous_workspace_policy,
    _validate_update_candidate,
)


class SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(
            database_path
        )
        self._initialize()

    def create(
        self,
        policy: EnterpriseWorkspaceProviderRoutingPolicy,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        _require_creatable_policy(
            policy
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            if _sqlite_policy_id_exists(
                connection=connection,
                policy_id=policy.policy_id,
            ):
                raise (
                    EnterpriseProviderRoutingPolicyAlreadyExistsError(
                        "enterprise provider routing policy "
                        "already exists: "
                        f"{policy.policy_id}"
                    )
                )

            if _sqlite_current_workspace_policy_exists(
                connection=connection,
                workspace_id=policy.workspace_id,
            ):
                raise (
                    EnterpriseProviderRoutingPolicyAlreadyExistsError(
                        "enterprise provider routing workspace "
                        "already has a non-archived policy"
                    )
                )

            _insert_policy(
                connection=connection,
                policy=policy,
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                EnterpriseProviderRoutingPolicyAlreadyExistsError(
                    "enterprise provider routing policy "
                    "creation violated persistence uniqueness"
                )
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
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_workspace_provider_routing_policies
                WHERE policy_id = ?
                """,
                (
                    policy_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _policy_from_row(
            row
        )

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM enterprise_workspace_provider_routing_policies
                WHERE workspace_id = ?
                  AND status != 'archived'
                ORDER BY policy_id ASC
                LIMIT 2
                """,
                (
                    workspace_id,
                ),
            ).fetchall()

        matches = tuple(
            _policy_from_row(row)
            for row in rows
        )

        return (
            _require_unambiguous_workspace_policy(
                matches
            )
        )

    def update(
        self,
        policy: EnterpriseWorkspaceProviderRoutingPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_workspace_provider_routing_policies
                WHERE policy_id = ?
                """,
                (
                    policy.policy_id,
                ),
            ).fetchone()

            if row is None:
                raise (
                    EnterpriseProviderRoutingPolicyNotFoundError(
                        "enterprise provider routing policy "
                        "not found: "
                        f"{policy.policy_id}"
                    )
                )

            stored = _policy_from_row(
                row
            )

            _validate_update_candidate(
                stored=stored,
                candidate=policy,
                expected_revision=expected_revision,
            )

            cursor = connection.execute(
                """
                UPDATE enterprise_workspace_provider_routing_policies
                SET
                    workspace_id = ?,
                    policy_version = ?,
                    status = ?,
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
                    policy.workspace_id,
                    policy.policy_version,
                    policy.status.value,
                    policy.revision,
                    policy.created_by_user_id,
                    _canonical_timestamp(
                        policy.created_at
                    ),
                    policy.updated_by_user_id,
                    _canonical_timestamp(
                        policy.updated_at
                    ),
                    policy.model_dump_json(),
                    policy.policy_id,
                    expected_revision,
                ),
            )

            if cursor.rowcount != 1:
                raise (
                    EnterpriseProviderRoutingPolicyRevisionConflictError(
                        "enterprise provider routing policy "
                        "revision conflict"
                    )
                )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                EnterpriseProviderRoutingPolicyIntegrityError(
                    "enterprise provider routing policy "
                    "update violated persistence integrity"
                )
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return policy

    def _initialize(
        self,
    ) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    enterprise_workspace_provider_routing_policies (
                        policy_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        policy_version TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        created_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_by_user_id TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_enterprise_provider_routing_current_workspace
                ON enterprise_workspace_provider_routing_policies (
                    workspace_id
                )
                WHERE status != 'archived';

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_provider_routing_workspace
                ON enterprise_workspace_provider_routing_policies (
                    workspace_id,
                    status,
                    policy_id
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(
                self._database_path
            )
        )
        connection.row_factory = (
            sqlite3.Row
        )
        return connection


def _insert_policy(
    *,
    connection: sqlite3.Connection,
    policy: EnterpriseWorkspaceProviderRoutingPolicy,
) -> None:
    connection.execute(
        """
        INSERT INTO enterprise_workspace_provider_routing_policies (
            policy_id,
            workspace_id,
            policy_version,
            status,
            revision,
            created_by_user_id,
            created_at,
            updated_by_user_id,
            updated_at,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            policy.policy_id,
            policy.workspace_id,
            policy.policy_version,
            policy.status.value,
            policy.revision,
            policy.created_by_user_id,
            _canonical_timestamp(
                policy.created_at
            ),
            policy.updated_by_user_id,
            _canonical_timestamp(
                policy.updated_at
            ),
            policy.model_dump_json(),
        ),
    )


def _policy_from_row(
    row: sqlite3.Row,
) -> EnterpriseWorkspaceProviderRoutingPolicy:
    return (
        EnterpriseWorkspaceProviderRoutingPolicy
        .model_validate_json(
            row["payload"]
        )
    )


def _canonical_timestamp(
    value,
) -> str:
    return value.isoformat()


def _sqlite_policy_id_exists(
    *,
    connection: sqlite3.Connection,
    policy_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM enterprise_workspace_provider_routing_policies
        WHERE policy_id = ?
        LIMIT 1
        """,
        (
            policy_id,
        ),
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
        FROM enterprise_workspace_provider_routing_policies
        WHERE workspace_id = ?
          AND status != 'archived'
        LIMIT 1
        """,
        (
            workspace_id,
        ),
    ).fetchone()

    return row is not None
