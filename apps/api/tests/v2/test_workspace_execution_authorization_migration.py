from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.v2.api.dependencies import V2Services
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _services() -> V2Services:
    return V2Services(
        workflow=RewriteWorkflow(),
    )


def _workspace(
    services: V2Services,
) -> tuple[str, str]:
    owner = services.workspace.create_user(
        email="d3-owner@example.com",
        display_name="D3 Owner",
    )

    workspace = (
        services.workspace_provisioning.create_workspace(
            user_id=owner.user_id,
            name="D3 Execution Workspace",
        )
    )

    return (
        owner.user_id,
        workspace.workspace_id,
    )


def _enterprise_only_member(
    *,
    services: V2Services,
    workspace_id: str,
    role: EnterpriseWorkspaceRole,
) -> str:
    user = services.workspace.create_user(
        email=f"d3-{role.value}@example.com",
        display_name=f"D3 {role.value}",
    )

    workspace = (
        services.enterprise_authorization
        .workspaces
        .get(workspace_id)
    )

    assert workspace is not None

    now = datetime.now(UTC)

    services.enterprise_authorization.memberships.create(
        EnterpriseWorkspaceMembership(
            membership_id=(
                f"membership_d3_{role.value}"
            ),
            organization_id=workspace.organization_id,
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


def test_container_wires_same_execution_gate_everywhere() -> None:
    services = _services()

    assert (
        services.rewrite._authorization_gate
        is services.workspace_authorization
    )

    assert (
        services.multi_candidate._authorization_gate
        is services.workspace_authorization
    )

    assert (
        services.long_document._authorization_gate
        is services.workspace_authorization
    )

    assert (
        services.history._authorization_gate
        is services.workspace_authorization
    )

    assert (
        services.long_document_audit._authorization_gate
        is services.workspace_authorization
    )


@pytest.mark.parametrize(
    ("role", "allowed"),
    (
        (
            EnterpriseWorkspaceRole.VIEWER,
            False,
        ),
        (
            EnterpriseWorkspaceRole.REVIEWER,
            False,
        ),
        (
            EnterpriseWorkspaceRole.EDITOR,
            True,
        ),
        (
            EnterpriseWorkspaceRole.ADMIN,
            True,
        ),
        (
            EnterpriseWorkspaceRole.OWNER,
            True,
        ),
    ),
)
def test_rewrite_execute_role_matrix(
    role: EnterpriseWorkspaceRole,
    allowed: bool,
) -> None:
    services = _services()

    _, workspace_id = _workspace(
        services
    )

    user_id = _enterprise_only_member(
        services=services,
        workspace_id=workspace_id,
        role=role,
    )

    if allowed:
        result = services.workspace_authorization.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=(
                EnterprisePermission.REWRITE_EXECUTE
            ),
        )

        assert (
            result.permission
            is EnterprisePermission.REWRITE_EXECUTE
        )
    else:
        with pytest.raises(
            PermissionError,
            match="permission_not_granted",
        ):
            services.workspace_authorization.require(
                workspace_id=workspace_id,
                user_id=user_id,
                permission=(
                    EnterprisePermission.REWRITE_EXECUTE
                ),
            )


def test_legacy_only_membership_is_not_execution_authority() -> None:
    services = _services()

    owner = services.workspace.create_user(
        email="d3-legacy-only@example.com",
        display_name="D3 Legacy Only",
    )

    workspace = services.workspace.create_workspace(
        user_id=owner.user_id,
        name="D3 Legacy Only Workspace",
    )

    services.workspace.require_membership(
        workspace_id=workspace.workspace_id,
        user_id=owner.user_id,
    )

    with pytest.raises(
        PermissionError,
        match="workspace_not_found",
    ):
        services.workspace_authorization.require(
            workspace_id=workspace.workspace_id,
            user_id=owner.user_id,
            permission=(
                EnterprisePermission.REWRITE_EXECUTE
            ),
        )
