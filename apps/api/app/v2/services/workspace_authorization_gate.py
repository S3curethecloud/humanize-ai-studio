from __future__ import annotations

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
    EnterpriseAuthorizationResult,
)


class WorkspaceAuthorizationGate:
    def __init__(
        self,
        *,
        resolver: EnterpriseAuthorizationResolver,
    ) -> None:
        self._resolver = resolver

    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> EnterpriseAuthorizationResult:
        resolution = self._resolver.resolve(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=permission,
        )

        if (
            resolution.status
            is not AuthorizationResolutionStatus.RESOLVED
        ):
            reason = resolution.failure_reason

            raise PermissionError(
                reason.value
                if reason is not None
                else "authorization_resolution_failed"
            )

        authorization = resolution.authorization

        if authorization is None:
            raise RuntimeError(
                "resolved enterprise authorization "
                "is missing authorization evidence"
            )

        if (
            authorization.decision
            is not AuthorizationDecision.ALLOW
        ):
            reason = authorization.denial_reason

            raise PermissionError(
                reason.value
                if reason is not None
                else "authorization_denied"
            )

        return authorization
