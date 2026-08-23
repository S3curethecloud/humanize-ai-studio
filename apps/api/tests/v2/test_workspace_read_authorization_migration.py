from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
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


def _period() -> tuple[
    datetime,
    datetime,
]:
    end = datetime.now(UTC)

    return (
        end - timedelta(hours=1),
        end,
    )


def _provision_workspace(
    services: V2Services,
) -> tuple[
    str,
    str,
]:
    owner = services.workspace.create_user(
        email="read-owner@example.com",
        display_name="Read Owner",
    )

    workspace = (
        services.workspace_provisioning.create_workspace(
            user_id=owner.user_id,
            name="Read Authority Workspace",
        )
    )

    return (
        owner.user_id,
        workspace.workspace_id,
    )


def _add_enterprise_viewer_without_legacy_membership(
    *,
    services: V2Services,
    workspace_id: str,
) -> str:
    viewer = services.workspace.create_user(
        email="read-viewer@example.com",
        display_name="Read Viewer",
    )

    enterprise_workspace = (
        services.enterprise_authorization
        .workspaces
        .get(workspace_id)
    )

    assert enterprise_workspace is not None

    now = datetime.now(UTC)

    services.enterprise_authorization.memberships.create(
        EnterpriseWorkspaceMembership(
            membership_id=(
                "membership_read_viewer"
            ),
            organization_id=(
                enterprise_workspace.organization_id
            ),
            workspace_id=workspace_id,
            user_id=viewer.user_id,
            role=EnterpriseWorkspaceRole.VIEWER,
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(
        PermissionError
    ):
        services.workspace.require_membership(
            workspace_id=workspace_id,
            user_id=viewer.user_id,
        )

    return viewer.user_id


def test_container_wires_same_enterprise_gate_to_read_services() -> None:
    services = _services()

    assert (
        services.history._authorization_gate
        is services.workspace_authorization
    )

    assert (
        services.workspace_analytics._authorization_gate
        is services.workspace_authorization
    )


def test_enterprise_viewer_can_read_analytics_without_legacy_membership() -> None:
    services = _services()

    _, workspace_id = _provision_workspace(
        services
    )

    viewer_id = (
        _add_enterprise_viewer_without_legacy_membership(
            services=services,
            workspace_id=workspace_id,
        )
    )

    period_start, period_end = _period()

    snapshot = services.workspace_analytics.query(
        workspace_id=workspace_id,
        user_id=viewer_id,
        period_start=period_start,
        period_end=period_end,
    )

    assert snapshot.workspace_id == workspace_id
    assert snapshot.event_count == 0


def test_enterprise_viewer_can_read_history_without_legacy_membership() -> None:
    services = _services()

    _, workspace_id = _provision_workspace(
        services
    )

    viewer_id = (
        _add_enterprise_viewer_without_legacy_membership(
            services=services,
            workspace_id=workspace_id,
        )
    )

    records = (
        services.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=viewer_id,
        )
    )

    assert records == ()


def test_legacy_only_workspace_is_not_sufficient_for_read_authority() -> None:
    services = _services()

    owner = services.workspace.create_user(
        email="legacy-only@example.com",
        display_name="Legacy Only",
    )

    workspace = services.workspace.create_workspace(
        user_id=owner.user_id,
        name="Legacy Only Workspace",
    )

    services.workspace.require_membership(
        workspace_id=workspace.workspace_id,
        user_id=owner.user_id,
    )

    period_start, period_end = _period()

    with pytest.raises(
        PermissionError,
        match="workspace_not_found",
    ):
        services.workspace_analytics.query(
            workspace_id=workspace.workspace_id,
            user_id=owner.user_id,
            period_start=period_start,
            period_end=period_end,
        )

    with pytest.raises(
        PermissionError,
        match="workspace_not_found",
    ):
        services.history.list_workspace_history(
            workspace_id=workspace.workspace_id,
            user_id=owner.user_id,
        )


def test_enterprise_membership_lifecycle_controls_read_authority() -> None:
    services = _services()

    owner_id, workspace_id = (
        _provision_workspace(
            services
        )
    )

    memberships = (
        services.enterprise_authorization
        .memberships
    )

    membership = memberships.get_current(
        workspace_id=workspace_id,
        user_id=owner_id,
    )

    assert membership is not None

    suspended = membership.model_copy(
        update={
            "status": (
                EnterpriseMembershipStatus.SUSPENDED
            ),
            "updated_at": (
                membership.updated_at
                + timedelta(seconds=1)
            ),
        }
    )

    memberships.update(
        suspended
    )

    period_start, period_end = _period()

    with pytest.raises(
        PermissionError,
        match="membership_not_active",
    ):
        services.workspace_analytics.query(
            workspace_id=workspace_id,
            user_id=owner_id,
            period_start=period_start,
            period_end=period_end,
        )

    with pytest.raises(
        PermissionError,
        match="membership_not_active",
    ):
        services.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=owner_id,
        )


def test_gate_denies_permission_not_granted() -> None:
    services = _services()

    _, workspace_id = _provision_workspace(
        services
    )

    viewer_id = (
        _add_enterprise_viewer_without_legacy_membership(
            services=services,
            workspace_id=workspace_id,
        )
    )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        services.workspace_authorization.require(
            workspace_id=workspace_id,
            user_id=viewer_id,
            permission=(
                EnterprisePermission.REWRITE_EXECUTE
            ),
        )
