from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseWorkspaceProviderRoutingOperation,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseProviderRoutingOperationAlreadyExistsError,
    EnterpriseProviderRoutingOperationIntegrityError,
    EnterpriseProviderRoutingOperationNotFoundError,
    EnterpriseProviderRoutingOperationRevisionConflictError,
    _require_creatable_operation,
    _validate_update_candidate,
)


class SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository:
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
        operation: EnterpriseWorkspaceProviderRoutingOperation,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        _require_creatable_operation(
            operation
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            _insert_operation(
                connection=connection,
                operation=operation,
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                EnterpriseProviderRoutingOperationAlreadyExistsError(
                    "enterprise provider routing operation "
                    "already exists or violated persistence "
                    "uniqueness: "
                    f"{operation.operation_id}"
                )
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return operation

    def get(
        self,
        operation_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_workspace_provider_routing_operations
                WHERE operation_id = ?
                """,
                (
                    operation_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return _operation_from_row(
            row
        )

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceProviderRoutingOperation,
        ...,
    ]:
        if (
            not workspace_id
            or workspace_id
            != workspace_id.strip()
        ):
            raise ValueError(
                "enterprise provider routing operation "
                "workspace_id must be normalized"
            )

        if (
            limit < 1
            or limit > 1000
        ):
            raise ValueError(
                "enterprise provider routing operation "
                "list limit must be between 1 and 1000"
            )

        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT payload
                FROM enterprise_workspace_provider_routing_operations
                WHERE workspace_id = ?
                ORDER BY
                    created_at DESC,
                    operation_id DESC
                LIMIT ?
                ''',
                (
                    workspace_id,
                    limit,
                ),
            ).fetchall()

        return tuple(
            EnterpriseWorkspaceProviderRoutingOperation
            .model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def update(
        self,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_workspace_provider_routing_operations
                WHERE operation_id = ?
                """,
                (
                    operation.operation_id,
                ),
            ).fetchone()

            if row is None:
                raise (
                    EnterpriseProviderRoutingOperationNotFoundError(
                        "enterprise provider routing operation "
                        "not found: "
                        f"{operation.operation_id}"
                    )
                )

            stored = _operation_from_row(
                row
            )

            _validate_update_candidate(
                stored=stored,
                candidate=operation,
                expected_revision=expected_revision,
            )

            cursor = connection.execute(
                """
                UPDATE enterprise_workspace_provider_routing_operations
                SET
                    workspace_id = ?,
                    user_id = ?,
                    operation_kind = ?,
                    policy_id = ?,
                    policy_revision = ?,
                    status = ?,
                    revision = ?,
                    created_at = ?,
                    updated_at = ?,
                    payload = ?
                WHERE operation_id = ?
                  AND revision = ?
                """,
                (
                    operation.workspace_id,
                    operation.user_id,
                    operation.operation_kind.value,
                    operation.policy_id,
                    operation.policy_revision,
                    operation.status.value,
                    operation.revision,
                    _canonical_timestamp(
                        operation.created_at
                    ),
                    _canonical_timestamp(
                        operation.updated_at
                    ),
                    operation.model_dump_json(),
                    operation.operation_id,
                    expected_revision,
                ),
            )

            if cursor.rowcount != 1:
                raise (
                    EnterpriseProviderRoutingOperationRevisionConflictError(
                        "enterprise provider routing operation "
                        "revision conflict"
                    )
                )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                EnterpriseProviderRoutingOperationIntegrityError(
                    "enterprise provider routing operation "
                    "update violated persistence integrity"
                )
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        return operation

    def _initialize(
        self,
    ) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    enterprise_workspace_provider_routing_operations (
                        operation_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        operation_kind TEXT NOT NULL,
                        policy_id TEXT NOT NULL,
                        policy_revision INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_provider_routing_operation_workspace
                ON enterprise_workspace_provider_routing_operations (
                    workspace_id,
                    status,
                    created_at,
                    operation_id
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_provider_routing_operation_status
                ON enterprise_workspace_provider_routing_operations (
                    status,
                    updated_at,
                    operation_id
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_provider_routing_operation_policy
                ON enterprise_workspace_provider_routing_operations (
                    policy_id,
                    policy_revision,
                    operation_id
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


def _insert_operation(
    *,
    connection: sqlite3.Connection,
    operation: EnterpriseWorkspaceProviderRoutingOperation,
) -> None:
    connection.execute(
        """
        INSERT INTO enterprise_workspace_provider_routing_operations (
            operation_id,
            workspace_id,
            user_id,
            operation_kind,
            policy_id,
            policy_revision,
            status,
            revision,
            created_at,
            updated_at,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            operation.operation_id,
            operation.workspace_id,
            operation.user_id,
            operation.operation_kind.value,
            operation.policy_id,
            operation.policy_revision,
            operation.status.value,
            operation.revision,
            _canonical_timestamp(
                operation.created_at
            ),
            _canonical_timestamp(
                operation.updated_at
            ),
            operation.model_dump_json(),
        ),
    )


def _operation_from_row(
    row: sqlite3.Row,
) -> EnterpriseWorkspaceProviderRoutingOperation:
    return (
        EnterpriseWorkspaceProviderRoutingOperation
        .model_validate_json(
            row["payload"]
        )
    )


def _canonical_timestamp(
    value: datetime,
) -> str:
    return value.isoformat()
