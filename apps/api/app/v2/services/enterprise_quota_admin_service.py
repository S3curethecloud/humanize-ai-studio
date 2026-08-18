from __future__ import annotations

from enum import StrEnum

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.repositories.enterprise_quota_admin_mutations import (
    EnterpriseQuotaAdminMutationRepository,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
    EnterpriseAdminAuditRecordInput,
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


class EnterpriseQuotaAdministrationAuditError(
    RuntimeError
):
    pass


class EnterpriseQuotaAdminService:
    def __init__(
        self,
        *,
        limits: EnterpriseQuotaLimitRepository,
        authorization_resolver: EnterpriseAuthorizationResolver,
        audit_recording: EnterpriseAdminAuditRecordingService,
        atomic_mutations: EnterpriseQuotaAdminMutationRepository,
    ) -> None:
        self._limits = limits
        self._authorization_resolver = authorization_resolver
        self._audit_recording = audit_recording
        self._atomic_mutations = atomic_mutations

    def create_limit(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        quota_limit: EnterpriseWorkspaceQuotaLimit,
    ) -> EnterpriseWorkspaceQuotaLimit:
        action = EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE

        try:
            self._require_permission(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                permission=EnterprisePermission.QUOTA_MANAGE,
            )
        except EnterpriseQuotaAdministrationError as exc:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.DENIED,
                target_type="quota_limit",
                target_id=quota_limit.quota_limit_id,
                failure_reason=exc.reason.value,
            )
            raise

        if quota_limit.workspace_id != workspace_id:
            reason = (
                QuotaAdministrationFailureReason.LIMIT_SCOPE_MISMATCH
            )
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_limit",
                target_id=quota_limit.quota_limit_id,
                failure_reason=reason.value,
            )
            raise EnterpriseQuotaAdministrationError(
                reason
            )

        try:
            success_event = self._audit_recording.build_event(
                EnterpriseAdminAuditRecordInput(
                    workspace_id=workspace_id,
                    actor_user_id=actor_user_id,
                    action=action,
                    outcome=(
                        EnterpriseAdminAuditOutcome.SUCCEEDED
                    ),
                    target_type="quota_limit",
                    target_id=quota_limit.quota_limit_id,
                )
            )

            created = (
                self._atomic_mutations.create_limit_with_audit(
                    quota_limit=quota_limit,
                    audit_event=success_event,
                )
            )
        except ValueError:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_limit",
                target_id=quota_limit.quota_limit_id,
                failure_reason=(
                    "quota_limit_persistence_rejected"
                ),
            )
            raise
        except Exception:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_limit",
                target_id=quota_limit.quota_limit_id,
                failure_reason=(
                    "quota_limit_persistence_failed"
                ),
            )
            raise

        return created

    def get_limit(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        quota_limit_id: str,
    ) -> EnterpriseWorkspaceQuotaLimit:
        action = EnterpriseAdminAuditAction.QUOTA_LIMIT_GET

        try:
            self._require_permission(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                permission=EnterprisePermission.QUOTA_READ,
            )
        except EnterpriseQuotaAdministrationError as exc:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.DENIED,
                target_type="quota_limit",
                target_id=quota_limit_id,
                failure_reason=exc.reason.value,
            )
            raise

        try:
            quota_limit = self._limits.get(
                quota_limit_id,
            )
        except Exception:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_limit",
                target_id=quota_limit_id,
                failure_reason="quota_limit_query_failed",
            )
            raise

        if (
            quota_limit is None
            or quota_limit.workspace_id != workspace_id
        ):
            reason = (
                QuotaAdministrationFailureReason.LIMIT_NOT_FOUND
            )
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_limit",
                target_id=quota_limit_id,
                failure_reason=reason.value,
            )
            raise EnterpriseQuotaAdministrationError(
                reason
            )

        self._record_audit(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
            target_type="quota_limit",
            target_id=quota_limit_id,
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
        action = EnterpriseAdminAuditAction.QUOTA_LIMIT_LIST

        try:
            self._require_permission(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                permission=EnterprisePermission.QUOTA_READ,
            )
        except EnterpriseQuotaAdministrationError as exc:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.DENIED,
                target_type="quota_dimension",
                target_id=dimension.value,
                failure_reason=exc.reason.value,
            )
            raise

        try:
            quota_limits = (
                self._limits.list_for_workspace_dimension(
                    workspace_id=workspace_id,
                    dimension=dimension,
                    limit=limit,
                )
            )
        except ValueError:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_dimension",
                target_id=dimension.value,
                failure_reason="quota_limit_query_rejected",
            )
            raise
        except Exception:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.FAILED,
                target_type="quota_dimension",
                target_id=dimension.value,
                failure_reason="quota_limit_query_failed",
            )
            raise

        self._record_audit(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
            target_type="quota_dimension",
            target_id=dimension.value,
        )

        return quota_limits

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

    def _record_audit(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: EnterpriseAdminAuditAction,
        outcome: EnterpriseAdminAuditOutcome,
        target_type: str,
        target_id: str,
        failure_reason: str | None = None,
    ) -> None:
        try:
            self._audit_recording.record(
                EnterpriseAdminAuditRecordInput(
                    workspace_id=workspace_id,
                    actor_user_id=actor_user_id,
                    action=action,
                    outcome=outcome,
                    target_type=target_type,
                    target_id=target_id,
                    failure_reason=failure_reason,
                )
            )
        except Exception as exc:
            raise EnterpriseQuotaAdministrationAuditError(
                "enterprise quota administration "
                "audit persistence failed"
            ) from exc
