from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.provider_routing import (
    RoutingPolicy,
)
from app.v2.repositories.enterprise_provider_routing_policies import (
    EnterpriseWorkspaceProviderRoutingPolicyRepository,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


EnterpriseProviderRoutingRuntimeIntegrityReason = Literal[
    "provider_routing_policy_resolution_failed",
    "provider_routing_policy_scope_mismatch",
    "provider_routing_policy_archived",
    "provider_routing_policy_derivation_failed",
]


class EnterpriseProviderRoutingRuntimeIntegrityError(
    RuntimeError
):
    def __init__(
        self,
        reason: EnterpriseProviderRoutingRuntimeIntegrityReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseProviderRoutingRuntimeContext:
    enterprise_policy: (
        EnterpriseWorkspaceProviderRoutingPolicy
    )
    execution_policy: RoutingPolicy

    @property
    def workspace_id(
        self,
    ) -> str:
        return self.enterprise_policy.workspace_id

    @property
    def policy_id(
        self,
    ) -> str:
        return self.enterprise_policy.policy_id

    @property
    def policy_revision(
        self,
    ) -> int:
        return self.enterprise_policy.revision


class EnterpriseProviderRoutingPolicyRuntimeService:
    def __init__(
        self,
        *,
        policies: EnterpriseWorkspaceProviderRoutingPolicyRepository,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._policies = policies
        self._authorization_gate = authorization_gate

    def resolve(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> EnterpriseProviderRoutingRuntimeContext | None:
        try:
            policy = self._policies.get_for_workspace(
                workspace_id
            )
        except Exception as exc:
            raise EnterpriseProviderRoutingRuntimeIntegrityError(
                "provider_routing_policy_resolution_failed"
            ) from exc

        if policy is None:
            return None

        if policy.workspace_id != workspace_id:
            raise EnterpriseProviderRoutingRuntimeIntegrityError(
                "provider_routing_policy_scope_mismatch"
            )

        if (
            policy.status
            is EnterpriseProviderRoutingPolicyStatus.ARCHIVED
        ):
            raise EnterpriseProviderRoutingRuntimeIntegrityError(
                "provider_routing_policy_archived"
            )

        if (
            policy.status
            is EnterpriseProviderRoutingPolicyStatus.DISABLED
        ):
            return None

        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=(
                EnterprisePermission.PROVIDER_POLICY_USE
            ),
        )

        try:
            execution_policy = (
                policy.to_execution_policy()
            )
        except Exception as exc:
            raise EnterpriseProviderRoutingRuntimeIntegrityError(
                "provider_routing_policy_derivation_failed"
            ) from exc

        return EnterpriseProviderRoutingRuntimeContext(
            enterprise_policy=policy,
            execution_policy=execution_policy,
        )
