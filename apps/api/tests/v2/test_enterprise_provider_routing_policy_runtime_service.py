from datetime import UTC, datetime

import pytest

from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.repositories.enterprise_provider_routing_policies import (
    InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository,
)
from app.v2.services.enterprise_provider_routing_policy_runtime_service import (
    EnterpriseProviderRoutingPolicyRuntimeService,
    EnterpriseProviderRoutingRuntimeIntegrityError,
)


NOW = datetime(
    2026,
    8,
    28,
    12,
    0,
    tzinfo=UTC,
)


class RecordingAuthorizationGate:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            tuple[
                str,
                str,
                EnterprisePermission,
            ]
        ] = []

    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> None:
        self.calls.append(
            (
                workspace_id,
                user_id,
                permission,
            )
        )


class WrongScopeRepository:
    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        return _policy(
            workspace_id="workspace-other"
        )


class FailingRepository:
    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None:
        raise RuntimeError(
            "repository unavailable"
        )


def _policy(
    **updates: object,
) -> EnterpriseWorkspaceProviderRoutingPolicy:
    payload: dict[str, object] = {
        "policy_id": "routing-policy-1",
        "workspace_id": "workspace-1",
        "status": (
            EnterpriseProviderRoutingPolicyStatus.ACTIVE
        ),
        "ordered_target_ids": (
            "deterministic-primary",
        ),
        "created_by_user_id": "owner-1",
        "created_at": NOW,
        "updated_by_user_id": "owner-1",
        "updated_at": NOW,
        "revision": 4,
    }
    payload.update(updates)

    return EnterpriseWorkspaceProviderRoutingPolicy(
        **payload
    )


def test_active_policy_resolves_execution_snapshot() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository()
    )
    gate = RecordingAuthorizationGate()

    policies.create(
        _policy(
            revision=1,
        )
    )

    service = (
        EnterpriseProviderRoutingPolicyRuntimeService(
            policies=policies,
            authorization_gate=gate,
        )
    )

    context = service.resolve(
        workspace_id="workspace-1",
        user_id="editor-1",
    )

    assert context is not None
    assert context.workspace_id == "workspace-1"
    assert context.policy_id == "routing-policy-1"
    assert context.policy_revision == 1

    assert (
        context.execution_policy.policy_id
        == "routing-policy-1"
    )
    assert (
        context.execution_policy.ordered_target_ids
        == ("deterministic-primary",)
    )

    assert gate.calls == [
        (
            "workspace-1",
            "editor-1",
            EnterprisePermission.PROVIDER_POLICY_USE,
        )
    ]


def test_no_workspace_policy_resolves_none() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository()
    )
    gate = RecordingAuthorizationGate()

    service = (
        EnterpriseProviderRoutingPolicyRuntimeService(
            policies=policies,
            authorization_gate=gate,
        )
    )

    assert (
        service.resolve(
            workspace_id="workspace-1",
            user_id="editor-1",
        )
        is None
    )

    assert gate.calls == []


def test_disabled_workspace_policy_resolves_none() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository()
    )
    gate = RecordingAuthorizationGate()

    policies.create(
        _policy(
            revision=1,
            status=(
                EnterpriseProviderRoutingPolicyStatus.DISABLED
            ),
        )
    )

    service = (
        EnterpriseProviderRoutingPolicyRuntimeService(
            policies=policies,
            authorization_gate=gate,
        )
    )

    assert (
        service.resolve(
            workspace_id="workspace-1",
            user_id="editor-1",
        )
        is None
    )

    assert gate.calls == []


def test_scope_mismatch_fails_closed() -> None:
    service = (
        EnterpriseProviderRoutingPolicyRuntimeService(
            policies=WrongScopeRepository(),
            authorization_gate=RecordingAuthorizationGate(),
        )
    )

    with pytest.raises(
        EnterpriseProviderRoutingRuntimeIntegrityError,
        match="provider_routing_policy_scope_mismatch",
    ):
        service.resolve(
            workspace_id="workspace-1",
            user_id="editor-1",
        )


def test_repository_failure_fails_closed() -> None:
    service = (
        EnterpriseProviderRoutingPolicyRuntimeService(
            policies=FailingRepository(),
            authorization_gate=RecordingAuthorizationGate(),
        )
    )

    with pytest.raises(
        EnterpriseProviderRoutingRuntimeIntegrityError,
        match="provider_routing_policy_resolution_failed",
    ):
        service.resolve(
            workspace_id="workspace-1",
            user_id="editor-1",
        )
