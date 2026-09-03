from datetime import (
    UTC,
    datetime,
    timedelta,
)

import pytest

from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.repositories.enterprise_provider_routing_policies import (
    EnterpriseProviderRoutingPolicyAlreadyExistsError,
    EnterpriseProviderRoutingPolicyRevisionConflictError,
)
from app.v2.repositories.enterprise_provider_routing_policies_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository,
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
        "created_by_user_id": "owner-1",
        "created_at": NOW,
        "updated_by_user_id": "owner-1",
        "updated_at": NOW,
        "revision": 1,
    }

    payload.update(
        updates
    )

    return (
        EnterpriseWorkspaceProviderRoutingPolicy(
            **payload
        )
    )


def test_sqlite_repository_persists_across_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "routing-policy.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
            database_path=database_path,
        )
    )

    policy = repository.create(
        _policy()
    )

    reopened = (
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
            database_path=database_path,
        )
    )

    assert (
        reopened.get_by_id(
            policy.policy_id
        )
        == policy
    )

    assert (
        reopened.get_for_workspace(
            policy.workspace_id
        )
        == policy
    )


def test_sqlite_repository_rejects_second_current_workspace_policy(
    tmp_path,
) -> None:
    repository = (
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
            database_path=(
                tmp_path
                / "routing-policy.sqlite3"
            ),
        )
    )

    repository.create(
        _policy()
    )

    with pytest.raises(
        EnterpriseProviderRoutingPolicyAlreadyExistsError,
        match="already has a non-archived policy",
    ):
        repository.create(
            _policy(
                policy_id="routing-policy-2",
            )
        )


def test_sqlite_repository_requires_expected_revision(
    tmp_path,
) -> None:
    repository = (
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
            database_path=(
                tmp_path
                / "routing-policy.sqlite3"
            ),
        )
    )

    original = repository.create(
        _policy()
    )

    candidate = original.model_copy(
        update={
            "revision": 2,
            "updated_by_user_id": (
                "admin-1"
            ),
            "updated_at": (
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        }
    )

    with pytest.raises(
        EnterpriseProviderRoutingPolicyRevisionConflictError,
        match="revision conflict",
    ):
        repository.update(
            candidate,
            expected_revision=99,
        )


def test_sqlite_archive_releases_workspace_identity(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "routing-policy.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
            database_path=database_path,
        )
    )

    original = repository.create(
        _policy()
    )

    archived = original.model_copy(
        update={
            "status": (
                EnterpriseProviderRoutingPolicyStatus.ARCHIVED
            ),
            "revision": 2,
            "updated_by_user_id": (
                "admin-1"
            ),
            "updated_at": (
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        }
    )

    repository.update(
        archived,
        expected_revision=1,
    )

    assert (
        repository.get_for_workspace(
            "workspace-1"
        )
        is None
    )

    replacement = repository.create(
        _policy(
            policy_id="routing-policy-2",
        )
    )

    reopened = (
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
            database_path=database_path,
        )
    )

    assert (
        reopened.get_for_workspace(
            "workspace-1"
        )
        == replacement
    )
