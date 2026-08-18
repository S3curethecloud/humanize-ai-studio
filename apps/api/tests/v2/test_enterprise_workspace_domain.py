from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_workspace import (
    ENTERPRISE_MEMBERSHIP_VERSION,
    ENTERPRISE_WORKSPACE_VERSION,
    EnterpriseMembershipStatus,
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
    EnterpriseWorkspaceStatus,
)

NOW = datetime(
    2026,
    8,
    13,
    8,
    0,
    tzinfo=UTC,
)


def _organization(
    **updates: object,
) -> EnterpriseOrganization:
    values: dict[str, object] = {
        "organization_id": "org_test",
        "name": "Test Organization",
        "created_by_user_id": "user_owner",
        "created_at": NOW,
    }

    values.update(updates)

    return EnterpriseOrganization(**values)


def _workspace(
    **updates: object,
) -> EnterpriseWorkspace:
    values: dict[str, object] = {
        "workspace_id": "workspace_test",
        "organization_id": "org_test",
        "name": "Enterprise Workspace",
        "created_by_user_id": "user_owner",
        "status": EnterpriseWorkspaceStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspace(**values)


def _membership(
    **updates: object,
) -> EnterpriseWorkspaceMembership:
    values: dict[str, object] = {
        "membership_id": "membership_test",
        "organization_id": "org_test",
        "workspace_id": "workspace_test",
        "user_id": "user_owner",
        "role": EnterpriseWorkspaceRole.OWNER,
        "status": EnterpriseMembershipStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspaceMembership(**values)


def test_versions_are_frozen() -> None:
    assert ENTERPRISE_WORKSPACE_VERSION == "enterprise-workspace-v1"

    assert ENTERPRISE_MEMBERSHIP_VERSION == "enterprise-membership-v1"


def test_enterprise_role_vocabulary_is_frozen() -> None:
    assert tuple(EnterpriseWorkspaceRole) == (
        EnterpriseWorkspaceRole.OWNER,
        EnterpriseWorkspaceRole.ADMIN,
        EnterpriseWorkspaceRole.EDITOR,
        EnterpriseWorkspaceRole.REVIEWER,
        EnterpriseWorkspaceRole.VIEWER,
    )


def test_workspace_status_vocabulary_is_frozen() -> None:
    assert tuple(EnterpriseWorkspaceStatus) == (
        EnterpriseWorkspaceStatus.ACTIVE,
        EnterpriseWorkspaceStatus.SUSPENDED,
        EnterpriseWorkspaceStatus.ARCHIVED,
    )


def test_membership_status_vocabulary_is_frozen() -> None:
    assert tuple(EnterpriseMembershipStatus) == (
        EnterpriseMembershipStatus.ACTIVE,
        EnterpriseMembershipStatus.SUSPENDED,
        EnterpriseMembershipStatus.REMOVED,
    )


def test_organization_is_immutable_and_forbids_extra_fields() -> None:
    organization = _organization()

    with pytest.raises(ValidationError):
        organization.name = "Mutated"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        EnterpriseOrganization.model_validate(
            {
                **organization.model_dump(),
                "unexpected": "field",
            }
        )


def test_workspace_is_immutable_and_forbids_extra_fields() -> None:
    workspace = _workspace()

    with pytest.raises(ValidationError):
        workspace.name = "Mutated"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        EnterpriseWorkspace.model_validate(
            {
                **workspace.model_dump(),
                "unexpected": "field",
            }
        )


def test_membership_is_immutable_and_forbids_extra_fields() -> None:
    membership = _membership()

    with pytest.raises(ValidationError):
        membership.role = (  # type: ignore[misc]
            EnterpriseWorkspaceRole.ADMIN
        )

    with pytest.raises(ValidationError):
        EnterpriseWorkspaceMembership.model_validate(
            {
                **membership.model_dump(),
                "unexpected": "field",
            }
        )


@pytest.mark.parametrize(
    ("factory", "field_name"),
    (
        (_organization, "created_at"),
        (_workspace, "created_at"),
        (_workspace, "updated_at"),
        (_membership, "created_at"),
        (_membership, "updated_at"),
    ),
)
def test_enterprise_records_require_timezone_aware_timestamps(
    factory: object,
    field_name: str,
) -> None:
    naive = datetime(
        2026,
        8,
        13,
        8,
        0,
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        factory(**{field_name: naive})  # type: ignore[operator]


def test_workspace_updated_at_cannot_precede_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        _workspace(
            updated_at=NOW - timedelta(seconds=1),
        )


def test_membership_updated_at_cannot_precede_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        _membership(
            updated_at=NOW - timedelta(seconds=1),
        )


def test_workspace_requires_organization_binding() -> None:
    workspace = _workspace()

    assert workspace.organization_id == "org_test"
    assert workspace.workspace_id == "workspace_test"


def test_membership_requires_organization_and_workspace_binding() -> None:
    membership = _membership()

    assert membership.organization_id == "org_test"
    assert membership.workspace_id == "workspace_test"
    assert membership.user_id == "user_owner"


@pytest.mark.parametrize(
    "role",
    tuple(EnterpriseWorkspaceRole),
)
def test_membership_accepts_every_frozen_role(
    role: EnterpriseWorkspaceRole,
) -> None:
    membership = _membership(
        role=role,
    )

    assert membership.role is role


@pytest.mark.parametrize(
    "status",
    tuple(EnterpriseMembershipStatus),
)
def test_membership_accepts_every_frozen_status(
    status: EnterpriseMembershipStatus,
) -> None:
    membership = _membership(
        status=status,
    )

    assert membership.status is status


def test_removed_membership_remains_historical_record() -> None:
    membership = _membership(
        status=EnterpriseMembershipStatus.REMOVED,
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    assert membership.status is EnterpriseMembershipStatus.REMOVED
    assert membership.role is EnterpriseWorkspaceRole.VIEWER
