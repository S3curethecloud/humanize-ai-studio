from __future__ import annotations

import pytest

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.services.workspace_provider_catalog_query_service import (
    WorkspaceProviderCatalogQueryService,
)


def _target(
    target_id: str = "target-a",
) -> ProviderModelTarget:
    provider_id = f"provider-{target_id}"

    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name=f"Provider {target_id}",
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=f"model-{target_id}",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        ),
        enabled=True,
    )


class _AuthorizationGateSpy:
    def __init__(
        self,
        sequence: list[tuple[object, ...]],
        *,
        deny: bool = False,
    ) -> None:
        self._sequence = sequence
        self._deny = deny

    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> None:
        self._sequence.append(
            (
                "authorize",
                workspace_id,
                user_id,
                permission,
            )
        )

        if self._deny:
            raise PermissionError(
                "permission_not_granted"
            )


class _CatalogSpy:
    def __init__(
        self,
        sequence: list[tuple[object, ...]],
        *,
        targets: tuple[
            ProviderModelTarget,
            ...,
        ] = (),
    ) -> None:
        self._sequence = sequence
        self._targets = targets
        self.calls: list[
            tuple[
                bool,
                int,
            ]
        ] = []

    def list_targets(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]:
        self.calls.append(
            (
                enabled_only,
                limit,
            )
        )
        self._sequence.append(
            (
                "catalog",
                enabled_only,
                limit,
            )
        )
        return self._targets


def test_authorizes_provider_policy_read_before_catalog_access(
) -> None:
    sequence: list[
        tuple[
            object,
            ...,
        ]
    ] = []

    target = _target()

    authorization = _AuthorizationGateSpy(
        sequence
    )
    catalog = _CatalogSpy(
        sequence,
        targets=(
            target,
        ),
    )

    service = WorkspaceProviderCatalogQueryService(
        catalog=catalog,
        authorization_gate=authorization,
    )

    result = service.list_targets(
        workspace_id="workspace-test",
        user_id="user-test",
    )

    assert result == (
        target,
    )

    assert sequence == [
        (
            "authorize",
            "workspace-test",
            "user-test",
            EnterprisePermission.PROVIDER_POLICY_READ,
        ),
        (
            "catalog",
            False,
            1000,
        ),
    ]


def test_forwards_enabled_filter_and_limit(
) -> None:
    sequence: list[
        tuple[
            object,
            ...,
        ]
    ] = []

    catalog = _CatalogSpy(
        sequence
    )

    service = WorkspaceProviderCatalogQueryService(
        catalog=catalog,
        authorization_gate=(
            _AuthorizationGateSpy(
                sequence
            )
        ),
    )

    service.list_targets(
        workspace_id="workspace-test",
        user_id="user-test",
        enabled_only=True,
        limit=17,
    )

    assert catalog.calls == [
        (
            True,
            17,
        )
    ]


def test_authorization_denial_occurs_before_catalog_read(
) -> None:
    sequence: list[
        tuple[
            object,
            ...,
        ]
    ] = []

    catalog = _CatalogSpy(
        sequence
    )

    service = WorkspaceProviderCatalogQueryService(
        catalog=catalog,
        authorization_gate=(
            _AuthorizationGateSpy(
                sequence,
                deny=True,
            )
        ),
    )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        service.list_targets(
            workspace_id="workspace-test",
            user_id="user-test",
        )

    assert catalog.calls == []

    assert sequence == [
        (
            "authorize",
            "workspace-test",
            "user-test",
            EnterprisePermission.PROVIDER_POLICY_READ,
        )
    ]
