from __future__ import annotations

from app.v2.domain.enterprise_rbac import EnterprisePermission


class AllowAllWorkspaceAuthorizationGate:
    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> None:
        return None


def allow_all_workspace_authorization_gate() -> (
    AllowAllWorkspaceAuthorizationGate
):
    return AllowAllWorkspaceAuthorizationGate()


class DenyAllWorkspaceAuthorizationGate:
    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> None:
        raise PermissionError("permission_not_granted")


def deny_all_workspace_authorization_gate() -> (
    DenyAllWorkspaceAuthorizationGate
):
    return DenyAllWorkspaceAuthorizationGate()


class DenyPermissionWorkspaceAuthorizationGate:
    def __init__(
        self,
        *,
        denied_permission: EnterprisePermission,
    ) -> None:
        self._denied_permission = denied_permission

    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> None:
        if permission is self._denied_permission:
            raise PermissionError("permission_not_granted")


def deny_permission_workspace_authorization_gate(
    permission: EnterprisePermission,
) -> DenyPermissionWorkspaceAuthorizationGate:
    return DenyPermissionWorkspaceAuthorizationGate(
        denied_permission=permission,
    )
