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
)
from app.v2.repositories.enterprise_workspace import (
    EnterpriseMembershipRepository,
    EnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_service import (
    EnterpriseAuthorizationResult,
    EnterpriseAuthorizationService,
)

ENTERPRISE_AUTHORIZATION_RESOLUTION_VERSION: Literal["enterprise-authorization-resolution-v1"] = (
    "enterprise-authorization-resolution-v1"
)


class AuthorizationResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    RESOLUTION_FAILED = "resolution_failed"


class AuthorizationResolutionFailureReason(StrEnum):
    WORKSPACE_NOT_FOUND = "workspace_not_found"
    MEMBERSHIP_NOT_FOUND = "membership_not_found"


class EnterpriseAuthorizationResolutionResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    resolution_version: Literal["enterprise-authorization-resolution-v1"] = (
        ENTERPRISE_AUTHORIZATION_RESOLUTION_VERSION
    )

    status: AuthorizationResolutionStatus
    workspace_id: str
    user_id: str
    permission: EnterprisePermission

    failure_reason: AuthorizationResolutionFailureReason | None = None

    authorization: EnterpriseAuthorizationResult | None = None

    @model_validator(mode="after")
    def require_resolution_integrity(
        self,
    ) -> EnterpriseAuthorizationResolutionResult:
        if self.status is AuthorizationResolutionStatus.RESOLVED:
            if self.failure_reason is not None:
                raise ValueError(
                    "resolved authorization cannot include a resolution failure reason"
                )

            if self.authorization is None:
                raise ValueError("resolved authorization requires an authorization result")

        if self.status is AuthorizationResolutionStatus.RESOLUTION_FAILED:
            if self.failure_reason is None:
                raise ValueError("failed authorization resolution requires a failure reason")

            if self.authorization is not None:
                raise ValueError(
                    "failed authorization resolution cannot include an authorization result"
                )

        return self


class EnterpriseAuthorizationResolver:
    def __init__(
        self,
        *,
        workspaces: EnterpriseWorkspaceRepository,
        memberships: EnterpriseMembershipRepository,
        authorization_service: EnterpriseAuthorizationService,
    ) -> None:
        self._workspaces = workspaces
        self._memberships = memberships
        self._authorization_service = authorization_service

    def resolve(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> EnterpriseAuthorizationResolutionResult:
        workspace = self._workspaces.get(workspace_id)

        if workspace is None:
            return self._resolution_failure(
                workspace_id=workspace_id,
                user_id=user_id,
                permission=permission,
                reason=(AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND),
            )

        membership = self._memberships.get_current(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        if membership is None:
            return self._resolution_failure(
                workspace_id=workspace_id,
                user_id=user_id,
                permission=permission,
                reason=(AuthorizationResolutionFailureReason.MEMBERSHIP_NOT_FOUND),
            )

        authorization = self._authorization_service.authorize(
            workspace=workspace,
            membership=membership,
            user_id=user_id,
            permission=permission,
        )

        return EnterpriseAuthorizationResolutionResult(
            status=AuthorizationResolutionStatus.RESOLVED,
            workspace_id=workspace_id,
            user_id=user_id,
            permission=permission,
            authorization=authorization,
        )

    @staticmethod
    def _resolution_failure(
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
        reason: AuthorizationResolutionFailureReason,
    ) -> EnterpriseAuthorizationResolutionResult:
        return EnterpriseAuthorizationResolutionResult(
            status=(AuthorizationResolutionStatus.RESOLUTION_FAILED),
            workspace_id=workspace_id,
            user_id=user_id,
            permission=permission,
            failure_reason=reason,
        )
