from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
    role_has_permission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
    EnterpriseWorkspaceStatus,
)

ENTERPRISE_AUTHORIZATION_VERSION: Literal["enterprise-authorization-v1"] = (
    "enterprise-authorization-v1"
)


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class AuthorizationDenialReason(StrEnum):
    WORKSPACE_NOT_ACTIVE = "workspace_not_active"
    MEMBERSHIP_NOT_ACTIVE = "membership_not_active"
    SCOPE_MISMATCH = "scope_mismatch"
    PERMISSION_NOT_GRANTED = "permission_not_granted"


class EnterpriseAuthorizationResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    authorization_version: Literal["enterprise-authorization-v1"] = ENTERPRISE_AUTHORIZATION_VERSION

    decision: AuthorizationDecision
    permission: EnterprisePermission
    organization_id: str
    workspace_id: str
    membership_id: str
    user_id: str
    role: EnterpriseWorkspaceRole
    denial_reason: AuthorizationDenialReason | None = None

    @model_validator(mode="after")
    def require_decision_integrity(
        self,
    ) -> EnterpriseAuthorizationResult:
        if self.decision is AuthorizationDecision.ALLOW and self.denial_reason is not None:
            raise ValueError("allowed authorization cannot include a denial reason")

        if self.decision is AuthorizationDecision.DENY and self.denial_reason is None:
            raise ValueError("denied authorization requires a denial reason")

        return self


class EnterpriseAuthorizationService:
    def authorize(
        self,
        *,
        workspace: EnterpriseWorkspace,
        membership: EnterpriseWorkspaceMembership,
        user_id: str,
        permission: EnterprisePermission,
    ) -> EnterpriseAuthorizationResult:
        if workspace.status is not EnterpriseWorkspaceStatus.ACTIVE:
            return self._deny(
                workspace=workspace,
                membership=membership,
                user_id=user_id,
                permission=permission,
                reason=(AuthorizationDenialReason.WORKSPACE_NOT_ACTIVE),
            )

        if membership.status is not EnterpriseMembershipStatus.ACTIVE:
            return self._deny(
                workspace=workspace,
                membership=membership,
                user_id=user_id,
                permission=permission,
                reason=(AuthorizationDenialReason.MEMBERSHIP_NOT_ACTIVE),
            )

        if not self._scope_matches(
            workspace=workspace,
            membership=membership,
            user_id=user_id,
        ):
            return self._deny(
                workspace=workspace,
                membership=membership,
                user_id=user_id,
                permission=permission,
                reason=AuthorizationDenialReason.SCOPE_MISMATCH,
            )

        if not role_has_permission(
            membership.role,
            permission,
        ):
            return self._deny(
                workspace=workspace,
                membership=membership,
                user_id=user_id,
                permission=permission,
                reason=(AuthorizationDenialReason.PERMISSION_NOT_GRANTED),
            )

        return EnterpriseAuthorizationResult(
            decision=AuthorizationDecision.ALLOW,
            permission=permission,
            organization_id=workspace.organization_id,
            workspace_id=workspace.workspace_id,
            membership_id=membership.membership_id,
            user_id=user_id,
            role=membership.role,
        )

    @staticmethod
    def _scope_matches(
        *,
        workspace: EnterpriseWorkspace,
        membership: EnterpriseWorkspaceMembership,
        user_id: str,
    ) -> bool:
        return (
            membership.organization_id == workspace.organization_id
            and membership.workspace_id == workspace.workspace_id
            and membership.user_id == user_id
        )

    @staticmethod
    def _deny(
        *,
        workspace: EnterpriseWorkspace,
        membership: EnterpriseWorkspaceMembership,
        user_id: str,
        permission: EnterprisePermission,
        reason: AuthorizationDenialReason,
    ) -> EnterpriseAuthorizationResult:
        return EnterpriseAuthorizationResult(
            decision=AuthorizationDecision.DENY,
            permission=permission,
            organization_id=workspace.organization_id,
            workspace_id=workspace.workspace_id,
            membership_id=membership.membership_id,
            user_id=user_id,
            role=membership.role,
            denial_reason=reason,
        )
