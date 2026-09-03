from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseWorkspaceEvaluationOperation,
)
from app.v2.repositories.enterprise_evaluation_operations import (
    EnterpriseEvaluationOperationAlreadyExistsError,
    EnterpriseEvaluationOperationIntegrityError,
    EnterpriseEvaluationOperationNotFoundError,
    EnterpriseEvaluationOperationRevisionConflictError,
    _require_binding_lookup_key,
    _require_creatable_operation,
    _single_binding_lookup_match,
    _validate_update_candidate,
)


class SQLiteEnterpriseWorkspaceEvaluationOperationRepository:
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
        operation: EnterpriseWorkspaceEvaluationOperation,
    ) -> EnterpriseWorkspaceEvaluationOperation:
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
                EnterpriseEvaluationOperationAlreadyExistsError(
                    "enterprise evaluation operation "
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
    ) -> EnterpriseWorkspaceEvaluationOperation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    operation_id,
                    workspace_id,
                    actor_user_id,
                    run_id,
                    dataset_id,
                    dataset_version,
                    target_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    payload
                FROM enterprise_workspace_evaluation_operations
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
        EnterpriseWorkspaceEvaluationOperation,
        ...,
    ]:
        if (
            not workspace_id
            or workspace_id != workspace_id.strip()
        ):
            raise ValueError(
                "enterprise evaluation operation "
                "workspace_id must be normalized"
            )

        if limit < 1 or limit > 1000:
            raise ValueError(
                "enterprise evaluation operation "
                "list limit must be between 1 and 1000"
            )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    operation_id,
                    workspace_id,
                    actor_user_id,
                    run_id,
                    dataset_id,
                    dataset_version,
                    target_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    payload
                FROM enterprise_workspace_evaluation_operations
                WHERE workspace_id = ?
                ORDER BY
                    created_at DESC,
                    operation_id DESC
                LIMIT ?
                """,
                (
                    workspace_id,
                    limit,
                ),
            ).fetchall()

        return tuple(
            _operation_from_row(
                row
            )
            for row in rows
        )


    def find_by_binding_for_workspace(
        self,
        *,
        workspace_id: str,
        binding_id: str,
    ) -> EnterpriseWorkspaceEvaluationOperation | None:
        _require_binding_lookup_key(
            workspace_id=workspace_id,
            binding_id=binding_id,
        )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    operation_id,
                    workspace_id,
                    actor_user_id,
                    run_id,
                    dataset_id,
                    dataset_version,
                    target_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    payload
                FROM enterprise_workspace_evaluation_operations
                WHERE workspace_id = ?
                ORDER BY operation_id ASC
                """,
                (
                    workspace_id,
                ),
            ).fetchall()

        operations = tuple(
            _operation_from_row(
                row
            )
            for row in rows
        )

        matches = tuple(
            operation
            for operation in operations
            if (
                operation.workspace_id == workspace_id
                and any(
                    binding.binding_id == binding_id
                    for binding
                    in operation.evidence_bindings
                )
            )
        )

        return _single_binding_lookup_match(
            workspace_id=workspace_id,
            binding_id=binding_id,
            matches=matches,
        )

    def update(
        self,
        operation: EnterpriseWorkspaceEvaluationOperation,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT
                    operation_id,
                    workspace_id,
                    actor_user_id,
                    run_id,
                    dataset_id,
                    dataset_version,
                    target_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    payload
                FROM enterprise_workspace_evaluation_operations
                WHERE operation_id = ?
                """,
                (
                    operation.operation_id,
                ),
            ).fetchone()

            if row is None:
                raise (
                    EnterpriseEvaluationOperationNotFoundError(
                        "enterprise evaluation operation "
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
                UPDATE enterprise_workspace_evaluation_operations
                SET
                    workspace_id = ?,
                    actor_user_id = ?,
                    run_id = ?,
                    dataset_id = ?,
                    dataset_version = ?,
                    target_id = ?,
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
                    operation.actor_user_id,
                    operation.run_id,
                    operation.dataset_id,
                    operation.dataset_version,
                    operation.target_id,
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
                    EnterpriseEvaluationOperationRevisionConflictError(
                        "enterprise evaluation operation "
                        "revision conflict"
                    )
                )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                EnterpriseEvaluationOperationIntegrityError(
                    "enterprise evaluation operation "
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
                    enterprise_workspace_evaluation_operations (
                        operation_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        actor_user_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL,
                        dataset_version TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_evaluation_operation_workspace
                ON enterprise_workspace_evaluation_operations (
                    workspace_id,
                    status,
                    created_at,
                    operation_id
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_evaluation_operation_status
                ON enterprise_workspace_evaluation_operations (
                    status,
                    updated_at,
                    operation_id
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_evaluation_operation_run
                ON enterprise_workspace_evaluation_operations (
                    run_id,
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
    operation: EnterpriseWorkspaceEvaluationOperation,
) -> None:
    connection.execute(
        """
        INSERT INTO enterprise_workspace_evaluation_operations (
            operation_id,
            workspace_id,
            actor_user_id,
            run_id,
            dataset_id,
            dataset_version,
            target_id,
            status,
            revision,
            created_at,
            updated_at,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            operation.operation_id,
            operation.workspace_id,
            operation.actor_user_id,
            operation.run_id,
            operation.dataset_id,
            operation.dataset_version,
            operation.target_id,
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
) -> EnterpriseWorkspaceEvaluationOperation:
    try:
        operation = (
            EnterpriseWorkspaceEvaluationOperation
            .model_validate_json(
                row["payload"]
            )
        )

    except Exception as exc:
        raise EnterpriseEvaluationOperationIntegrityError(
            "persisted enterprise evaluation operation "
            "payload is invalid"
        ) from exc

    _require_row_payload_integrity(
        row=row,
        operation=operation,
    )

    return operation


def _require_row_payload_integrity(
    *,
    row: sqlite3.Row,
    operation: EnterpriseWorkspaceEvaluationOperation,
) -> None:
    expected = {
        "operation_id": operation.operation_id,
        "workspace_id": operation.workspace_id,
        "actor_user_id": operation.actor_user_id,
        "run_id": operation.run_id,
        "dataset_id": operation.dataset_id,
        "dataset_version": operation.dataset_version,
        "target_id": operation.target_id,
        "status": operation.status.value,
        "revision": operation.revision,
        "created_at": _canonical_timestamp(
            operation.created_at
        ),
        "updated_at": _canonical_timestamp(
            operation.updated_at
        ),
    }

    for field_name, expected_value in expected.items():
        if row[field_name] != expected_value:
            raise EnterpriseEvaluationOperationIntegrityError(
                "persisted enterprise evaluation operation "
                "row does not match authoritative payload: "
                f"{field_name}"
            )



def _canonical_timestamp(
    value: datetime,
) -> str:
    return value.isoformat()
