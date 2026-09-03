from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_provider_routing_policy import (
    ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_POLICY_VERSION,
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
)


NOW = datetime(
    2026,
    8,
    28,
    12,
    0,
    tzinfo=UTC,
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
        "fallback_policy": FallbackPolicy(),
        "created_by_user_id": "owner-1",
        "created_at": NOW,
        "updated_by_user_id": "owner-1",
        "updated_at": NOW,
        "revision": 1,
    }
    payload.update(updates)

    return EnterpriseWorkspaceProviderRoutingPolicy(
        **payload
    )


def test_enterprise_policy_derives_existing_execution_policy() -> None:
    policy = _policy()

    execution = policy.to_execution_policy()

    assert (
        policy.policy_version
        == ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_POLICY_VERSION
    )
    assert execution.policy_id == policy.policy_id
    assert (
        execution.ordered_target_ids
        == policy.ordered_target_ids
    )
    assert (
        execution.fallback_policy
        == policy.fallback_policy
    )


def test_enterprise_policy_normalizes_identifiers() -> None:
    policy = _policy(
        policy_id="  routing-policy-1  ",
        workspace_id="  workspace-1  ",
        created_by_user_id="  owner-1  ",
        updated_by_user_id="  owner-2  ",
    )

    assert policy.policy_id == "routing-policy-1"
    assert policy.workspace_id == "workspace-1"
    assert policy.created_by_user_id == "owner-1"
    assert policy.updated_by_user_id == "owner-2"


def test_enterprise_policy_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _policy(
            created_at=datetime(
                2026,
                8,
                28,
                12,
                0,
            )
        )


def test_enterprise_policy_reuses_routing_target_integrity() -> None:
    with pytest.raises(
        ValidationError,
        match="target IDs must be unique",
    ):
        _policy(
            ordered_target_ids=(
                "deterministic-primary",
                "deterministic-primary",
            ),
            fallback_policy=FallbackPolicy(
                enabled=True,
                failure_categories=(
                    "provider",
                ),
            ),
        )
