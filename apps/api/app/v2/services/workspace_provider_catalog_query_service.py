from __future__ import annotations

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.provider_routing import (
    ProviderModelTarget,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class WorkspaceProviderCatalogQueryService:
    def __init__(
        self,
        *,
        catalog: ProviderCatalogRepository,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._catalog = catalog
        self._authorization_gate = authorization_gate

    def list_targets(
        self,
        *,
        workspace_id: str,
        user_id: str,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=(
                EnterprisePermission.PROVIDER_POLICY_READ
            ),
        )

        return self._catalog.list_targets(
            enabled_only=enabled_only,
            limit=limit,
        )
