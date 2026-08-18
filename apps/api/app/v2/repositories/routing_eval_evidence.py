from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.eval_ops import EvaluationRunOutcome
from app.v2.domain.provider_routing import RoutingDecisionStatus
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
)


class RoutingEvidenceRepository(Protocol):
    def create(
        self,
        record: RoutingEvidenceRecord,
    ) -> RoutingEvidenceRecord: ...

    def get(
        self,
        evidence_id: str,
    ) -> RoutingEvidenceRecord | None: ...

    def list_records(
        self,
        *,
        policy_id: str | None = None,
        decision_status: RoutingDecisionStatus | None = None,
        execution_outcome: RoutingEvidenceExecutionOutcome | None = None,
        executed_target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[RoutingEvidenceRecord, ...]: ...


class EvaluationEvidenceRepository(Protocol):
    def create(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceRecord: ...

    def get(
        self,
        evidence_id: str,
    ) -> EvaluationEvidenceRecord | None: ...

    def list_records(
        self,
        *,
        run_id: str | None = None,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        run_outcome: EvaluationRunOutcome | None = None,
        gate_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationEvidenceRecord, ...]: ...


class InMemoryRoutingEvidenceRepository:
    def __init__(self) -> None:
        self._records: dict[
            str,
            RoutingEvidenceRecord,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        record: RoutingEvidenceRecord,
    ) -> RoutingEvidenceRecord:
        with self._lock:
            if record.evidence_id in self._records:
                raise ValueError(
                    "routing evidence already exists: "
                    f"{record.evidence_id}"
                )

            candidate = dict(self._records)
            candidate[record.evidence_id] = record
            self._records = candidate

        return record

    def get(
        self,
        evidence_id: str,
    ) -> RoutingEvidenceRecord | None:
        with self._lock:
            return self._records.get(evidence_id)

    def list_records(
        self,
        *,
        policy_id: str | None = None,
        decision_status: RoutingDecisionStatus | None = None,
        execution_outcome: RoutingEvidenceExecutionOutcome | None = None,
        executed_target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[RoutingEvidenceRecord, ...]:
        _require_list_limit(
            limit=limit,
            evidence_type="routing",
        )

        with self._lock:
            matches = (
                record
                for record in self._records.values()
                if _routing_matches(
                    record=record,
                    policy_id=policy_id,
                    decision_status=decision_status,
                    execution_outcome=execution_outcome,
                    executed_target_id=executed_target_id,
                )
            )

            ordered = sorted(
                matches,
                key=_routing_sort_key,
            )

            return tuple(ordered[:limit])


class InMemoryEvaluationEvidenceRepository:
    def __init__(self) -> None:
        self._records: dict[
            str,
            EvaluationEvidenceRecord,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceRecord:
        with self._lock:
            if record.evidence_id in self._records:
                raise ValueError(
                    "evaluation evidence already exists: "
                    f"{record.evidence_id}"
                )

            candidate = dict(self._records)
            candidate[record.evidence_id] = record
            self._records = candidate

        return record

    def get(
        self,
        evidence_id: str,
    ) -> EvaluationEvidenceRecord | None:
        with self._lock:
            return self._records.get(evidence_id)

    def list_records(
        self,
        *,
        run_id: str | None = None,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        run_outcome: EvaluationRunOutcome | None = None,
        gate_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationEvidenceRecord, ...]:
        _require_list_limit(
            limit=limit,
            evidence_type="evaluation",
        )

        with self._lock:
            matches = (
                record
                for record in self._records.values()
                if _evaluation_matches(
                    record=record,
                    run_id=run_id,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    target_id=target_id,
                    run_outcome=run_outcome,
                    gate_id=gate_id,
                )
            )

            ordered = sorted(
                matches,
                key=_evaluation_sort_key,
            )

            return tuple(ordered[:limit])


class SQLiteRoutingEvidenceRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        record: RoutingEvidenceRecord,
    ) -> RoutingEvidenceRecord:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_evidence_exists(
                connection=connection,
                table="routing_evidence",
                evidence_id=record.evidence_id,
            ):
                raise ValueError(
                    "routing evidence already exists: "
                    f"{record.evidence_id}"
                )

            connection.execute(
                """
                INSERT INTO routing_evidence (
                    evidence_id,
                    observed_at_utc,
                    policy_id,
                    decision_status,
                    execution_outcome,
                    executed_target_id,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evidence_id,
                    _observed_at_utc(record.observed_at),
                    record.policy.policy_id,
                    record.decision.status.value,
                    record.execution_outcome.value,
                    record.executed_target_id,
                    record.model_dump_json(),
                ),
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return record

    def get(
        self,
        evidence_id: str,
    ) -> RoutingEvidenceRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM routing_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        return RoutingEvidenceRecord.model_validate_json(
            row["payload"]
        )

    def list_records(
        self,
        *,
        policy_id: str | None = None,
        decision_status: RoutingDecisionStatus | None = None,
        execution_outcome: RoutingEvidenceExecutionOutcome | None = None,
        executed_target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[RoutingEvidenceRecord, ...]:
        _require_list_limit(
            limit=limit,
            evidence_type="routing",
        )

        conditions: list[str] = []
        parameters: list[object] = []

        if policy_id is not None:
            conditions.append("policy_id = ?")
            parameters.append(policy_id)

        if decision_status is not None:
            conditions.append("decision_status = ?")
            parameters.append(decision_status.value)

        if execution_outcome is not None:
            conditions.append("execution_outcome = ?")
            parameters.append(execution_outcome.value)

        if executed_target_id is not None:
            conditions.append("executed_target_id = ?")
            parameters.append(executed_target_id)

        where_clause = _where_clause(conditions)
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload
                FROM routing_evidence
                {where_clause}
                ORDER BY
                    observed_at_utc ASC,
                    evidence_id ASC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()

        return tuple(
            RoutingEvidenceRecord.model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    routing_evidence (
                        evidence_id TEXT PRIMARY KEY,
                        observed_at_utc TEXT NOT NULL,
                        policy_id TEXT NOT NULL,
                        decision_status TEXT NOT NULL,
                        execution_outcome TEXT NOT NULL,
                        executed_target_id TEXT,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_routing_evidence_observed
                ON routing_evidence (
                    observed_at_utc ASC,
                    evidence_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_routing_evidence_policy
                ON routing_evidence (
                    policy_id ASC,
                    observed_at_utc ASC,
                    evidence_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_routing_evidence_target
                ON routing_evidence (
                    executed_target_id ASC,
                    observed_at_utc ASC,
                    evidence_id ASC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self._database_path)
        )
        connection.row_factory = sqlite3.Row
        return connection


class SQLiteEvaluationEvidenceRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceRecord:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_evidence_exists(
                connection=connection,
                table="evaluation_evidence",
                evidence_id=record.evidence_id,
            ):
                raise ValueError(
                    "evaluation evidence already exists: "
                    f"{record.evidence_id}"
                )

            dataset = record.run.identity.dataset
            gate_id = (
                record.gate_result.gate.gate_id
                if record.gate_result is not None
                else None
            )

            connection.execute(
                """
                INSERT INTO evaluation_evidence (
                    evidence_id,
                    observed_at_utc,
                    run_id,
                    dataset_id,
                    dataset_version,
                    target_id,
                    run_outcome,
                    gate_id,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evidence_id,
                    _observed_at_utc(record.observed_at),
                    record.run.identity.run_id,
                    dataset.dataset_id,
                    dataset.dataset_version,
                    record.run.identity.target_id,
                    record.run.outcome.value,
                    gate_id,
                    record.model_dump_json(),
                ),
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return record

    def get(
        self,
        evidence_id: str,
    ) -> EvaluationEvidenceRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM evaluation_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        return EvaluationEvidenceRecord.model_validate_json(
            row["payload"]
        )

    def list_records(
        self,
        *,
        run_id: str | None = None,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        run_outcome: EvaluationRunOutcome | None = None,
        gate_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationEvidenceRecord, ...]:
        _require_list_limit(
            limit=limit,
            evidence_type="evaluation",
        )

        conditions: list[str] = []
        parameters: list[object] = []

        filter_values = (
            ("run_id", run_id),
            ("dataset_id", dataset_id),
            ("dataset_version", dataset_version),
            ("target_id", target_id),
            (
                "run_outcome",
                (
                    run_outcome.value
                    if run_outcome is not None
                    else None
                ),
            ),
            ("gate_id", gate_id),
        )

        for column, value in filter_values:
            if value is not None:
                conditions.append(
                    f"{column} = ?"
                )
                parameters.append(value)

        where_clause = _where_clause(conditions)
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload
                FROM evaluation_evidence
                {where_clause}
                ORDER BY
                    observed_at_utc ASC,
                    evidence_id ASC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()

        return tuple(
            EvaluationEvidenceRecord.model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    evaluation_evidence (
                        evidence_id TEXT PRIMARY KEY,
                        observed_at_utc TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL,
                        dataset_version TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        run_outcome TEXT NOT NULL,
                        gate_id TEXT,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_evidence_observed
                ON evaluation_evidence (
                    observed_at_utc ASC,
                    evidence_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_evidence_run
                ON evaluation_evidence (
                    run_id ASC,
                    observed_at_utc ASC,
                    evidence_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_evidence_dataset
                ON evaluation_evidence (
                    dataset_id ASC,
                    dataset_version ASC,
                    observed_at_utc ASC,
                    evidence_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_evidence_target
                ON evaluation_evidence (
                    target_id ASC,
                    observed_at_utc ASC,
                    evidence_id ASC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self._database_path)
        )
        connection.row_factory = sqlite3.Row
        return connection


def _routing_matches(
    *,
    record: RoutingEvidenceRecord,
    policy_id: str | None,
    decision_status: RoutingDecisionStatus | None,
    execution_outcome: RoutingEvidenceExecutionOutcome | None,
    executed_target_id: str | None,
) -> bool:
    if (
        policy_id is not None
        and record.policy.policy_id != policy_id
    ):
        return False

    if (
        decision_status is not None
        and record.decision.status is not decision_status
    ):
        return False

    if (
        execution_outcome is not None
        and record.execution_outcome is not execution_outcome
    ):
        return False

    return not (
        executed_target_id is not None
        and record.executed_target_id != executed_target_id
    )


def _evaluation_matches(
    *,
    record: EvaluationEvidenceRecord,
    run_id: str | None,
    dataset_id: str | None,
    dataset_version: str | None,
    target_id: str | None,
    run_outcome: EvaluationRunOutcome | None,
    gate_id: str | None,
) -> bool:
    identity = record.run.identity
    dataset = identity.dataset

    if run_id is not None and identity.run_id != run_id:
        return False

    if (
        dataset_id is not None
        and dataset.dataset_id != dataset_id
    ):
        return False

    if (
        dataset_version is not None
        and dataset.dataset_version != dataset_version
    ):
        return False

    if (
        target_id is not None
        and identity.target_id != target_id
    ):
        return False

    if (
        run_outcome is not None
        and record.run.outcome is not run_outcome
    ):
        return False

    if gate_id is None:
        return True

    return (
        record.gate_result is not None
        and record.gate_result.gate.gate_id == gate_id
    )


def _routing_sort_key(
    record: RoutingEvidenceRecord,
) -> tuple[object, str]:
    return (
        record.observed_at.astimezone(UTC),
        record.evidence_id,
    )


def _evaluation_sort_key(
    record: EvaluationEvidenceRecord,
) -> tuple[object, str]:
    return (
        record.observed_at.astimezone(UTC),
        record.evidence_id,
    )


def _observed_at_utc(
    value: datetime,
) -> str:
    return value.astimezone(UTC).isoformat()


def _where_clause(
    conditions: list[str],
) -> str:
    if not conditions:
        return ""

    return "WHERE " + " AND ".join(conditions)


def _sqlite_evidence_exists(
    *,
    connection: sqlite3.Connection,
    table: str,
    evidence_id: str,
) -> bool:
    if table not in {
        "routing_evidence",
        "evaluation_evidence",
    }:
        raise ValueError(
            "unsupported evidence table"
        )

    row = connection.execute(
        f"""
        SELECT 1
        FROM {table}
        WHERE evidence_id = ?
        LIMIT 1
        """,
        (evidence_id,),
    ).fetchone()

    return row is not None


def _require_list_limit(
    *,
    limit: int,
    evidence_type: str,
) -> None:
    if limit < 1 or limit > 10000:
        raise ValueError(
            f"{evidence_type} evidence list limit must be "
            "between 1 and 10000"
        )
