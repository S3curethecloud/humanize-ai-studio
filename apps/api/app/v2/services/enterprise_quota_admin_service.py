from __future__ import annotations

from enum import StrEnum

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
)


class QuotaAdministrationFailureReason(StrEnum):
    AUTHORIZATION_RESOLUTION_FAILED = (
        "authorization_resolution_failed"
    )
    AUTHORIZATION_DENIED = "authorization_denied"
    LIMIT_NOT_FOUND = "limit_not_found"
    LIMIT_SCOPE_MISMATCH = "limit_scope_mismatch"


class EnterpriseQuotaAdministrationError(RuntimeError):
    def __init__(
        self,
        reason: QuotaAdministrationFailureReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason.value)


class EnterpriseQuotaAdminService:
    def __init__(
        self,
        *,
        limits: EnterpriseQuotaLimitRepository,
        authorization_resolver: EnterpriseAuthorizationResolver,
    ) -> None:
        self._limits = limits
        self._authorization_resolver = authorization_resolver

    def create_limit(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        quota_limit: EnterpriseWorkspaceQuotaLimit,
    ) -> EnterpriseWorkspaceQuotaLimit:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.QUOTA_MANAGE,
        )

        if quota_limit.workspace_id != workspace_id:
            raise EnterpriseQuotaAdministrationError(
                QuotaAdministrationFailureReason.LIMIT_SCOPE_MISMATCH
            )

        return self._limits.create(quota_limit)

    def get_limit(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        quota_limit_id: str,
    ) -> EnterpriseWorkspaceQuotaLimit:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.QUOTA_READ,
        )

        quota_limit = self._limits.get(
            quota_limit_id,
        )

        if (
            quota_limit is None
            or quota_limit.workspace_id != workspace_id
        ):
            raise EnterpriseQuotaAdministrationError(
                QuotaAdministrationFailureReason.LIMIT_NOT_FOUND
            )

        return quota_limit

    def list_limits(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ]:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.QUOTA_READ,
        )

        return self._limits.list_for_workspace_dimension(
            workspace_id=workspace_id,
            dimension=dimension,
            limit=limit,
        )

    def _require_permission(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        permission: EnterprisePermission,
    ) -> None:
        resolution = self._authorization_resolver.resolve(
            workspace_id=workspace_id,
            user_id=actor_user_id,
            permission=permission,
        )

        if (
            resolution.status
            is not AuthorizationResolutionStatus.RESOLVED
        ):
            raise EnterpriseQuotaAdministrationError(
                QuotaAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED
            )

        authorization = resolution.authorization

        if (
            authorization is None
            or authorization.decision
            is not AuthorizationDecision.ALLOW
        ):
            raise EnterpriseQuotaAdministrationError(
                QuotaAdministrationFailureReason.AUTHORIZATION_DENIED
            )
