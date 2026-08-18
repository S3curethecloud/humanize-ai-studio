from __future__ import annotations

from unittest.mock import MagicMock

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
)
from app.v2.services.provider_catalog_provisioning_service import (
    ProviderCatalogDeclarationError,
    ProviderCatalogDriftError,
    ProviderCatalogProvisioningError,
    ProviderCatalogProvisioningService,
)


def _target(
    *,
    target_id: str,
    provider_id: str = "provider",
    model_id: str = "model",
    enabled: bool = True,
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name=provider_id,
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=model_id,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        ),
        enabled=enabled,
    )


def test_provisions_explicit_targets() -> None:
    catalog = InMemoryProviderCatalogRepository()
    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    primary = _target(
        target_id="primary",
        provider_id="provider-a",
        model_id="model-a",
    )
    secondary = _target(
        target_id="secondary",
        provider_id="provider-b",
        model_id="model-b",
        enabled=False,
    )

    result = service.provision(
        targets=(
            primary,
            secondary,
        ),
    )

    assert result.targets == (
        primary,
        secondary,
    )
    assert result.created_target_ids == (
        "primary",
        "secondary",
    )
    assert catalog.get("primary") == primary
    assert catalog.get("secondary") == secondary


def test_identical_reprovisioning_is_idempotent() -> None:
    catalog = InMemoryProviderCatalogRepository()
    target = _target(
        target_id="primary",
    )
    catalog.create(target)

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    result = service.provision(
        targets=(target,),
    )

    assert result.targets == (target,)
    assert result.created_target_ids == ()
    assert catalog.list_targets() == (
        target,
    )


def test_target_drift_fails_before_any_write() -> None:
    catalog = InMemoryProviderCatalogRepository()

    persisted = _target(
        target_id="primary",
        enabled=True,
    )
    catalog.create(persisted)

    new_target = _target(
        target_id="new-target",
        provider_id="new-provider",
        model_id="new-model",
    )
    drifted = _target(
        target_id="primary",
        enabled=False,
    )

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderCatalogDriftError,
        match="does not match persisted target",
    ):
        service.provision(
            targets=(
                new_target,
                drifted,
            ),
        )

    assert catalog.get(
        "new-target"
    ) is None
    assert catalog.get("primary") == persisted


def test_existing_provider_model_alias_fails_before_write() -> None:
    catalog = InMemoryProviderCatalogRepository()

    persisted = _target(
        target_id="persisted",
        provider_id="provider",
        model_id="model",
    )
    catalog.create(persisted)

    new_target = _target(
        target_id="new-target",
        provider_id="new-provider",
        model_id="new-model",
    )
    aliased = _target(
        target_id="alias",
        provider_id="provider",
        model_id="model",
    )

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderCatalogDriftError,
        match="different target",
    ):
        service.provision(
            targets=(
                new_target,
                aliased,
            ),
        )

    assert catalog.get(
        "new-target"
    ) is None
    assert catalog.get(
        "alias"
    ) is None


def test_duplicate_target_declarations_fail_before_catalog_access() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )

    target = _target(
        target_id="primary",
    )

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderCatalogDeclarationError,
        match="unique target IDs",
    ):
        service.provision(
            targets=(
                target,
                target,
            ),
        )

    catalog.list_targets.assert_not_called()
    catalog.create.assert_not_called()


def test_duplicate_provider_model_declarations_fail() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderCatalogDeclarationError,
        match="unique provider/model pairs",
    ):
        service.provision(
            targets=(
                _target(
                    target_id="primary",
                ),
                _target(
                    target_id="secondary",
                ),
            ),
        )

    catalog.list_targets.assert_not_called()
    catalog.create.assert_not_called()


def test_empty_declaration_fails_explicitly() -> None:
    service = ProviderCatalogProvisioningService(
        catalog=MagicMock(
            spec=ProviderCatalogRepository,
        ),
    )

    with pytest.raises(
        ProviderCatalogDeclarationError,
        match="at least one target",
    ):
        service.provision(
            targets=(),
        )


def test_catalog_listing_failure_is_wrapped() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.list_targets.side_effect = RuntimeError(
        "database unavailable",
    )

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderCatalogProvisioningError,
        match="listing failed",
    ) as captured:
        service.provision(
            targets=(
                _target(
                    target_id="primary",
                ),
            ),
        )

    assert isinstance(
        captured.value.__cause__,
        RuntimeError,
    )


def test_create_failure_is_wrapped() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.list_targets.return_value = ()
    catalog.create.side_effect = RuntimeError(
        "database unavailable",
    )

    service = ProviderCatalogProvisioningService(
        catalog=catalog,
    )

    with pytest.raises(
        ProviderCatalogProvisioningError,
        match="target provisioning failed",
    ) as captured:
        service.provision(
            targets=(
                _target(
                    target_id="primary",
                ),
            ),
        )

    assert isinstance(
        captured.value.__cause__,
        RuntimeError,
    )
