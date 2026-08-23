from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.v2.api.dependencies import V2Services
from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)


def _workspace_fixture() -> tuple[
    V2Services,
    str,
    str,
]:
    services = V2Services()

    owner = services.workspace.create_user(
        email=f"audit-owner-{uuid4().hex}@example.com",
        display_name="Audit Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=owner.user_id,
        name="Audit Authorization Workspace",
    )

    return (
        services,
        owner.user_id,
        workspace.workspace_id,
    )


def _enterprise_only_user(
    services: V2Services,
    *,
    workspace_id: str,
    role: EnterpriseWorkspaceRole,
) -> str:
    user = services.workspace.create_user(
        email=f"audit-{role.value}-{uuid4().hex}@example.com",
        display_name=f"Audit {role.value}",
    )

    enterprise_workspace = (
        services.enterprise_authorization.workspaces.get(
            workspace_id
        )
    )

    assert enterprise_workspace is not None

    now = datetime.now(UTC)

    services.enterprise_authorization.memberships.create(
        EnterpriseWorkspaceMembership(
            membership_id=(
                f"audit-membership-{role.value}-{uuid4().hex}"
            ),
            organization_id=(
                enterprise_workspace.organization_id
            ),
            workspace_id=workspace_id,
            user_id=user.user_id,
            role=role,
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(PermissionError):
        services.workspace.require_membership(
            workspace_id=workspace_id,
            user_id=user.user_id,
        )

    return user.user_id


def test_production_audit_service_uses_enterprise_gate() -> None:
    services = V2Services()

    assert (
        services.long_document_audit._authorization_gate
        is services.workspace_authorization
    )


@pytest.mark.parametrize(
    "role",
    (
        EnterpriseWorkspaceRole.VIEWER,
        EnterpriseWorkspaceRole.EDITOR,
    ),
)
def test_roles_without_audit_read_cannot_read_audit(
    role: EnterpriseWorkspaceRole,
) -> None:
    services, _, workspace_id = _workspace_fixture()

    user_id = _enterprise_only_user(
        services,
        workspace_id=workspace_id,
        role=role,
    )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        services.long_document_audit.get(
            workspace_id=workspace_id,
            user_id=user_id,
            audit_id="missing-audit",
        )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        services.long_document_audit.list_workspace(
            workspace_id=workspace_id,
            user_id=user_id,
        )


@pytest.mark.parametrize(
    "role",
    (
        EnterpriseWorkspaceRole.REVIEWER,
        EnterpriseWorkspaceRole.ADMIN,
        EnterpriseWorkspaceRole.OWNER,
    ),
)
def test_roles_with_audit_read_can_query_without_legacy_membership(
    role: EnterpriseWorkspaceRole,
) -> None:
    services, _, workspace_id = _workspace_fixture()

    user_id = _enterprise_only_user(
        services,
        workspace_id=workspace_id,
        role=role,
    )

    assert (
        services.long_document_audit.get(
            workspace_id=workspace_id,
            user_id=user_id,
            audit_id="missing-audit",
        )
        is None
    )

    assert (
        services.long_document_audit.list_workspace(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        == ()
    )


def test_legacy_only_workspace_cannot_satisfy_enterprise_audit_read() -> None:
    services = V2Services()

    user = services.workspace.create_user(
        email=f"legacy-audit-{uuid4().hex}@example.com",
        display_name="Legacy Audit User",
    )

    workspace = services.workspace.create_workspace(
        user_id=user.user_id,
        name="Legacy Audit Workspace",
    )

    services.workspace.require_membership(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
    )

    with pytest.raises(
        PermissionError,
        match="workspace_not_found",
    ):
        services.long_document_audit.list_workspace(
            workspace_id=workspace.workspace_id,
            user_id=user.user_id,
        )
