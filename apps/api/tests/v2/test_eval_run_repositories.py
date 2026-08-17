from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
    InMemoryEvaluationRunRepository,
    SQLiteEvaluationRunRepository,
)

RepositoryFactory = Callable[
    [],
    EvaluationRunRepository,
]


def _record(
    *,
    run_id: str = "run-001",
    dataset_id: str = "rewrite-quality",
    dataset_version: str = "v1",
    target_id: str = "openai-primary",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
) -> EvaluationRunRecord:
    identity = EvaluationRunIdentity(
        run_id=run_id,
        dataset=EvaluationDatasetIdentity(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
        ),
        target_id=target_id,
    )

    if outcome is EvaluationRunOutcome.FAILED:
        return EvaluationRunRecord(
            identity=identity,
            outcome=outcome,
            evaluated_case_count=2,
            failed_case_count=1,
            failure_reason="provider execution failed",
        )

    return EvaluationRunRecord(
        identity=identity,
        outcome=outcome,
        evaluated_case_count=2,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=EvaluationMetric.NATURALNESS,
                value=0.91,
            ),
            EvaluationMetricResult(
                metric=EvaluationMetric.LATENCY_MS,
                value=125.0,
            ),
        ),
    )


@pytest.fixture(
    params=[
        "memory",
        "sqlite",
    ]
)
def repository_factory(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> RepositoryFactory:
    if request.param == "memory":
        return InMemoryEvaluationRunRepository

    database_path = (
        tmp_path
        / "evaluation-runs.sqlite3"
    )

    return lambda: SQLiteEvaluationRunRepository(
        database_path=database_path
    )


def test_create_returns_exact_record(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    record = _record()

    assert repository.create(record) == record


def test_get_returns_created_record(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    record = _record()

    repository.create(record)

    assert (
        repository.get(record.identity.run_id)
        == record
    )


def test_get_unknown_run_returns_none(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    assert repository.get("missing-run") is None


def test_duplicate_run_id_is_rejected(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _record(
            run_id="duplicate-run",
            target_id="target-a",
        )
    )

    with pytest.raises(
        ValueError,
        match="evaluation run already exists",
    ):
        repository.create(
            _record(
                run_id="duplicate-run",
                target_id="target-b",
            )
        )


def test_different_run_ids_allow_same_dataset_and_target(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    first = _record(
        run_id="run-001"
    )
    second = _record(
        run_id="run-002"
    )

    repository.create(first)
    repository.create(second)

    assert repository.get("run-001") == first
    assert repository.get("run-002") == second


def test_list_is_deterministically_ordered_by_run_id(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    for run_id in (
        "run-003",
        "run-001",
        "run-002",
    ):
        repository.create(
            _record(
                run_id=run_id
            )
        )

    assert tuple(
        record.identity.run_id
        for record in repository.list_runs()
    ) == (
        "run-001",
        "run-002",
        "run-003",
    )


def test_list_filters_by_dataset_id(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _record(
            run_id="run-a",
            dataset_id="dataset-a",
        )
    )
    repository.create(
        _record(
            run_id="run-b",
            dataset_id="dataset-b",
        )
    )

    listed = repository.list_runs(
        dataset_id="dataset-a"
    )

    assert tuple(
        record.identity.run_id
        for record in listed
    ) == ("run-a",)


def test_list_filters_by_dataset_version(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _record(
            run_id="run-v1",
            dataset_version="v1",
        )
    )
    repository.create(
        _record(
            run_id="run-v2",
            dataset_version="v2",
        )
    )

    listed = repository.list_runs(
        dataset_version="v2"
    )

    assert tuple(
        record.identity.run_id
        for record in listed
    ) == ("run-v2",)


def test_list_filters_by_target_id(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _record(
            run_id="run-a",
            target_id="target-a",
        )
    )
    repository.create(
        _record(
            run_id="run-b",
            target_id="target-b",
        )
    )

    listed = repository.list_runs(
        target_id="target-b"
    )

    assert tuple(
        record.identity.run_id
        for record in listed
    ) == ("run-b",)


def test_list_combines_filters(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _record(
            run_id="match",
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-a",
        )
    )
    repository.create(
        _record(
            run_id="wrong-version",
            dataset_id="dataset-a",
            dataset_version="v1",
            target_id="target-a",
        )
    )
    repository.create(
        _record(
            run_id="wrong-target",
            dataset_id="dataset-a",
            dataset_version="v2",
            target_id="target-b",
        )
    )

    listed = repository.list_runs(
        dataset_id="dataset-a",
        dataset_version="v2",
        target_id="target-a",
    )

    assert tuple(
        record.identity.run_id
        for record in listed
    ) == ("match",)


def test_list_unknown_filter_returns_empty(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(_record())

    assert (
        repository.list_runs(
            dataset_id="missing"
        )
        == ()
    )


def test_list_limit_applies_after_ordering(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    for run_id in (
        "run-003",
        "run-001",
        "run-002",
    ):
        repository.create(
            _record(
                run_id=run_id
            )
        )

    listed = repository.list_runs(
        limit=2
    )

    assert tuple(
        record.identity.run_id
        for record in listed
    ) == (
        "run-001",
        "run-002",
    )


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        10001,
    ],
)
def test_list_rejects_invalid_limit(
    repository_factory: RepositoryFactory,
    limit: int,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        ValueError,
        match="between 1 and 10000",
    ):
        repository.list_runs(
            limit=limit
        )


@pytest.mark.parametrize(
    "outcome",
    list(EvaluationRunOutcome),
)
def test_payload_round_trip_preserves_run_record(
    repository_factory: RepositoryFactory,
    outcome: EvaluationRunOutcome,
) -> None:
    repository = repository_factory()

    record = _record(
        run_id=f"round-trip-{outcome.value}",
        dataset_id="dataset-special",
        dataset_version="2026-08-16",
        target_id="target-special",
        outcome=outcome,
    )

    repository.create(record)

    restored = repository.get(
        record.identity.run_id
    )

    assert restored == record


def test_create_does_not_mutate_record(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    record = _record()

    before = record.model_dump()

    repository.create(record)

    assert record.model_dump() == before


def test_memory_repository_instances_are_independent() -> None:
    first = InMemoryEvaluationRunRepository()
    second = InMemoryEvaluationRunRepository()

    first.create(_record())

    assert second.list_runs() == ()


def test_sqlite_persists_across_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path
        / "persistent-eval-runs.sqlite3"
    )

    first = SQLiteEvaluationRunRepository(
        database_path=database_path
    )
    record = _record()
    first.create(record)

    second = SQLiteEvaluationRunRepository(
        database_path=database_path
    )

    assert (
        second.get(record.identity.run_id)
        == record
    )


def test_sqlite_duplicate_rejection_persists_across_instances(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path
        / "persistent-eval-runs.sqlite3"
    )

    first = SQLiteEvaluationRunRepository(
        database_path=database_path
    )
    first.create(
        _record(
            run_id="persistent-run"
        )
    )

    second = SQLiteEvaluationRunRepository(
        database_path=database_path
    )

    with pytest.raises(
        ValueError,
        match="evaluation run already exists",
    ):
        second.create(
            _record(
                run_id="persistent-run",
                target_id="different-target",
            )
        )
