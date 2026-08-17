from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationDataset,
    EvaluationDatasetCase,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
)
from app.v2.repositories.eval_dataset import (
    EvaluationDatasetRepository,
    InMemoryEvaluationDatasetRepository,
    SQLiteEvaluationDatasetRepository,
)

RepositoryFactory = Callable[
    [],
    EvaluationDatasetRepository,
]


def _dataset(
    *,
    dataset_id: str = "rewrite-quality",
    dataset_version: str = "v1",
    case_id: str = "case-001",
    text: str = "Source text.",
) -> EvaluationDataset:
    return EvaluationDataset(
        identity=EvaluationDatasetIdentity(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
        ),
        cases=(
            EvaluationDatasetCase(
                case_id=case_id,
                input=EvaluationCaseInput(
                    text=text
                ),
            ),
        ),
    )


def _identity(
    *,
    dataset_id: str = "rewrite-quality",
    dataset_version: str = "v1",
) -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
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
        return InMemoryEvaluationDatasetRepository

    database_path = (
        tmp_path
        / "evaluation-datasets.sqlite3"
    )

    return lambda: SQLiteEvaluationDatasetRepository(
        database_path=database_path
    )


def test_create_returns_exact_dataset(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    dataset = _dataset()

    created = repository.create(dataset)

    assert created == dataset


def test_get_returns_created_dataset(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    dataset = _dataset()

    repository.create(dataset)

    assert (
        repository.get(dataset.identity)
        == dataset
    )


def test_get_unknown_identity_returns_none(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    assert (
        repository.get(
            _identity(
                dataset_id="missing",
                dataset_version="v1",
            )
        )
        is None
    )


def test_duplicate_dataset_version_is_rejected(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    dataset = _dataset()

    repository.create(dataset)

    with pytest.raises(
        ValueError,
        match="version already exists",
    ):
        repository.create(dataset)


def test_same_dataset_id_allows_multiple_versions(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    first = _dataset(
        dataset_version="v1"
    )
    second = _dataset(
        dataset_version="v2"
    )

    repository.create(first)
    repository.create(second)

    assert repository.get(first.identity) == first
    assert repository.get(second.identity) == second


def test_same_version_allowed_for_different_dataset_ids(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    first = _dataset(
        dataset_id="dataset-a",
        dataset_version="v1",
    )
    second = _dataset(
        dataset_id="dataset-b",
        dataset_version="v1",
    )

    repository.create(first)
    repository.create(second)

    assert repository.get(first.identity) == first
    assert repository.get(second.identity) == second


def test_list_is_deterministically_ordered(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    datasets = (
        _dataset(
            dataset_id="beta",
            dataset_version="v2",
        ),
        _dataset(
            dataset_id="alpha",
            dataset_version="v2",
        ),
        _dataset(
            dataset_id="alpha",
            dataset_version="v1",
        ),
        _dataset(
            dataset_id="beta",
            dataset_version="v1",
        ),
    )

    for dataset in datasets:
        repository.create(dataset)

    listed = repository.list_datasets()

    assert tuple(
        (
            dataset.identity.dataset_id,
            dataset.identity.dataset_version,
        )
        for dataset in listed
    ) == (
        ("alpha", "v1"),
        ("alpha", "v2"),
        ("beta", "v1"),
        ("beta", "v2"),
    )


def test_list_filters_by_dataset_id(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _dataset(
            dataset_id="alpha",
            dataset_version="v1",
        )
    )
    repository.create(
        _dataset(
            dataset_id="alpha",
            dataset_version="v2",
        )
    )
    repository.create(
        _dataset(
            dataset_id="beta",
            dataset_version="v1",
        )
    )

    listed = repository.list_datasets(
        dataset_id="alpha"
    )

    assert tuple(
        dataset.identity.dataset_version
        for dataset in listed
    ) == (
        "v1",
        "v2",
    )


def test_list_unknown_dataset_id_returns_empty(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _dataset()
    )

    assert (
        repository.list_datasets(
            dataset_id="missing"
        )
        == ()
    )


def test_list_limit_is_applied_after_ordering(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _dataset(
            dataset_version="v3"
        )
    )
    repository.create(
        _dataset(
            dataset_version="v1"
        )
    )
    repository.create(
        _dataset(
            dataset_version="v2"
        )
    )

    listed = repository.list_datasets(
        limit=2
    )

    assert tuple(
        dataset.identity.dataset_version
        for dataset in listed
    ) == (
        "v1",
        "v2",
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
        repository.list_datasets(
            limit=limit
        )


def test_payload_round_trip_preserves_full_dataset(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    dataset = _dataset(
        dataset_id="round-trip",
        dataset_version="2026-08-16",
        case_id="case-special",
        text="The launch is May 3 at 10:00.",
    )

    repository.create(dataset)

    restored = repository.get(
        dataset.identity
    )

    assert restored == dataset


def test_repository_create_does_not_mutate_dataset(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    dataset = _dataset()

    before = dataset.model_dump()

    repository.create(dataset)

    assert dataset.model_dump() == before


def test_repository_instances_are_independent_for_memory() -> None:
    first = InMemoryEvaluationDatasetRepository()
    second = InMemoryEvaluationDatasetRepository()

    first.create(
        _dataset()
    )

    assert second.list_datasets() == ()


def test_sqlite_persists_across_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path
        / "persistent.sqlite3"
    )

    first = SQLiteEvaluationDatasetRepository(
        database_path=database_path
    )
    dataset = _dataset()

    first.create(dataset)

    second = SQLiteEvaluationDatasetRepository(
        database_path=database_path
    )

    assert second.get(dataset.identity) == dataset


def test_sqlite_duplicate_rejection_persists_across_instances(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path
        / "persistent.sqlite3"
    )

    first = SQLiteEvaluationDatasetRepository(
        database_path=database_path
    )
    dataset = _dataset()
    first.create(dataset)

    second = SQLiteEvaluationDatasetRepository(
        database_path=database_path
    )

    with pytest.raises(
        ValueError,
        match="version already exists",
    ):
        second.create(dataset)
