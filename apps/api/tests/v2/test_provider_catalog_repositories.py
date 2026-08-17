from __future__ import annotations

from pathlib import Path

import pytest

from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
    ProviderCatalogRepository,
    SQLiteProviderCatalogRepository,
)


def _target(
    *,
    target_id: str,
    provider_id: str = "cloudflare",
    model_id: str | None = None,
    enabled: bool = True,
) -> ProviderModelTarget:
    resolved_model_id = (
        model_id
        if model_id is not None
        else f"{provider_id}/{target_id}"
    )

    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name=provider_id.title(),
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=resolved_model_id,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=enabled,
    )


@pytest.fixture(
    params=("memory", "sqlite"),
)
def repository(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> ProviderCatalogRepository:
    if request.param == "memory":
        return InMemoryProviderCatalogRepository()

    return SQLiteProviderCatalogRepository(
        database_path=tmp_path / "catalog.db",
    )


def test_create_and_get_round_trip(
    repository: ProviderCatalogRepository,
) -> None:
    target = _target(
        target_id="primary",
    )

    assert repository.create(target) == target
    assert repository.get("primary") == target


def test_get_missing_returns_none(
    repository: ProviderCatalogRepository,
) -> None:
    assert repository.get("missing") is None


def test_duplicate_target_id_is_rejected(
    repository: ProviderCatalogRepository,
) -> None:
    target = _target(
        target_id="primary",
    )
    repository.create(target)

    with pytest.raises(
        ValueError,
        match="target already exists",
    ):
        repository.create(target)


def test_duplicate_provider_model_pair_is_rejected(
    repository: ProviderCatalogRepository,
) -> None:
    repository.create(
        _target(
            target_id="first",
            provider_id="provider-a",
            model_id="shared-model",
        )
    )

    with pytest.raises(
        ValueError,
        match="provider/model pair already exists",
    ):
        repository.create(
            _target(
                target_id="second",
                provider_id="provider-a",
                model_id="shared-model",
            )
        )


def test_same_model_id_is_allowed_across_providers(
    repository: ProviderCatalogRepository,
) -> None:
    first = _target(
        target_id="first",
        provider_id="provider-a",
        model_id="shared-model",
    )
    second = _target(
        target_id="second",
        provider_id="provider-b",
        model_id="shared-model",
    )

    repository.create(first)
    repository.create(second)

    assert repository.get("first") == first
    assert repository.get("second") == second


def test_list_targets_is_ordered_by_target_id(
    repository: ProviderCatalogRepository,
) -> None:
    repository.create(
        _target(
            target_id="z-target",
        )
    )
    repository.create(
        _target(
            target_id="a-target",
        )
    )

    targets = repository.list_targets()

    assert tuple(
        target.target_id
        for target in targets
    ) == (
        "a-target",
        "z-target",
    )


def test_list_targets_can_filter_disabled_targets(
    repository: ProviderCatalogRepository,
) -> None:
    repository.create(
        _target(
            target_id="enabled",
            enabled=True,
        )
    )
    repository.create(
        _target(
            target_id="disabled",
            enabled=False,
        )
    )

    targets = repository.list_targets(
        enabled_only=True,
    )

    assert tuple(
        target.target_id
        for target in targets
    ) == ("enabled",)


def test_list_targets_includes_disabled_by_default(
    repository: ProviderCatalogRepository,
) -> None:
    repository.create(
        _target(
            target_id="enabled",
            enabled=True,
        )
    )
    repository.create(
        _target(
            target_id="disabled",
            enabled=False,
        )
    )

    targets = repository.list_targets()

    assert {
        target.target_id
        for target in targets
    } == {
        "enabled",
        "disabled",
    }


@pytest.mark.parametrize(
    "limit",
    (
        0,
        -1,
        10001,
    ),
)
def test_list_limit_is_validated(
    repository: ProviderCatalogRepository,
    limit: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 1 and 10000",
    ):
        repository.list_targets(
            limit=limit,
        )


def test_list_limit_is_applied_deterministically(
    repository: ProviderCatalogRepository,
) -> None:
    repository.create(
        _target(
            target_id="a",
        )
    )
    repository.create(
        _target(
            target_id="b",
        )
    )

    targets = repository.list_targets(
        limit=1,
    )

    assert tuple(
        target.target_id
        for target in targets
    ) == ("a",)


def test_sqlite_persists_across_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.db"

    first = SQLiteProviderCatalogRepository(
        database_path=database_path,
    )
    target = _target(
        target_id="persisted",
    )

    first.create(target)

    second = SQLiteProviderCatalogRepository(
        database_path=database_path,
    )

    assert second.get("persisted") == target
