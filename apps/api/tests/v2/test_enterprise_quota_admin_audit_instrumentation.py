from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceRole,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
    EnterpriseAdminAuditRecordInput,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionFailureReason,
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolutionResult,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
    AuthorizationDenialReason,
    EnterpriseAuthorizationResult,
)
from app.v2.services.enterprise_quota_admin_service import (
    EnterpriseQuotaAdministrationAuditError,
    EnterpriseQuotaAdministrationError,
    EnterpriseQuotaAdminService,
    QuotaAdministrationFailureReason,
)

WORKSPACE_ID = "workspace_test"
ACTOR_USER_ID = "user_admin"


def _quota_limit(
    *,
    workspace_id: str = WORKSPACE_ID,
) -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id="limit_requests",
        workspace_id=workspace_id,
        dimension=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS
        ),
        window=EnterpriseQuotaWindow(
            window_start=datetime(
                2026,
                8,
                1,
                tzinfo=UTC,
            ),
            window_end=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
        ),
        limit=100,
    )


def _authorization_result(
    *,
    permission: EnterprisePermission,
    decision: AuthorizationDecision,
) -> EnterpriseAuthorizationResult:
    return EnterpriseAuthorizationResult(
        decision=decision,
        permission=permission,
        organization_id="organization_test",
        workspace_id=WORKSPACE_ID,
        membership_id="membership_test",
        user_id=ACTOR_USER_ID,
        role=EnterpriseWorkspaceRole.ADMIN,
        denial_reason=(
            None
            if decision is AuthorizationDecision.ALLOW
            else (
                AuthorizationDenialReason.PERMISSION_NOT_GRANTED
            )
        ),
    )


def _resolved(
    *,
    permission: EnterprisePermission,
    decision: AuthorizationDecision = (
        AuthorizationDecision.ALLOW
    ),
) -> EnterpriseAuthorizationResolutionResult:
    return EnterpriseAuthorizationResolutionResult(
        status=AuthorizationResolutionStatus.RESOLVED,
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=permission,
        authorization=_authorization_result(
            permission=permission,
            decision=decision,
        ),
    )


def _resolution_failed(
    *,
    permission: EnterprisePermission,
) -> EnterpriseAuthorizationResolutionResult:
    return EnterpriseAuthorizationResolutionResult(
        status=(
            AuthorizationResolutionStatus.RESOLUTION_FAILED
        ),
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=permission,
        failure_reason=(
            AuthorizationResolutionFailureReason.MEMBERSHIP_NOT_FOUND
        ),
    )


def _service(
    *,
    resolution: EnterpriseAuthorizationResolutionResult,
) -> tuple[
    EnterpriseQuotaAdminService,
    InMemoryEnterpriseQuotaLimitRepository,
    MagicMock,
]:
    limits = InMemoryEnterpriseQuotaLimitRepository()

    resolver = MagicMock(
        spec=EnterpriseAuthorizationResolver,
    )
    resolver.resolve.return_value = resolution

    audit = MagicMock(
        spec=EnterpriseAdminAuditRecordingService,
    )

    service = EnterpriseQuotaAdminService(
        limits=limits,
        authorization_resolver=resolver,
        audit_recording=audit,
    )

    return service, limits, audit


def test_get_success_records_audit_success() -> None:
    service, limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )
    quota_limit = _quota_limit()
    limits.create(quota_limit)

    assert service.get_limit(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        quota_limit_id=quota_limit.quota_limit_id,
    ) == quota_limit

    audit.record.assert_called_once_with(
        EnterpriseAdminAuditRecordInput(
            workspace_id=WORKSPACE_ID,
            actor_user_id=ACTOR_USER_ID,
            action=(
                EnterpriseAdminAuditAction.QUOTA_LIMIT_GET
            ),
            outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
            target_type="quota_limit",
            target_id="limit_requests",
        )
    )


def test_list_success_records_audit_success() -> None:
    service, limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )
    limits.create(_quota_limit())

    service.list_limits(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        dimension=(
            EnterpriseQuotaDimension.REWRITE_REQUESTS
        ),
    )

    audit.record.assert_called_once_with(
        EnterpriseAdminAuditRecordInput(
            workspace_id=WORKSPACE_ID,
            actor_user_id=ACTOR_USER_ID,
            action=(
                EnterpriseAdminAuditAction.QUOTA_LIMIT_LIST
            ),
            outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
            target_type="quota_dimension",
            target_id="rewrite_requests",
        )
    )


def test_missing_get_records_failed_audit() -> None:
    service, _limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ) as exc_info:
        service.get_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit_id="missing",
        )

    assert (
        exc_info.value.reason
        is QuotaAdministrationFailureReason.LIMIT_NOT_FOUND
    )

    audit.record.assert_called_once_with(
        EnterpriseAdminAuditRecordInput(
            workspace_id=WORKSPACE_ID,
            actor_user_id=ACTOR_USER_ID,
            action=(
                EnterpriseAdminAuditAction.QUOTA_LIMIT_GET
            ),
            outcome=EnterpriseAdminAuditOutcome.FAILED,
            target_type="quota_limit",
            target_id="missing",
            failure_reason="limit_not_found",
        )
    )


def test_resolution_failure_records_denied_audit() -> None:
    service, _limits, audit = _service(
        resolution=_resolution_failed(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ):
        service.get_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit_id="limit_requests",
        )

    command = audit.record.call_args.args[0]

    assert (
        command.outcome
        is EnterpriseAdminAuditOutcome.DENIED
    )
    assert (
        command.failure_reason
        == "authorization_resolution_failed"
    )


def test_create_denial_records_denied_audit() -> None:
    service, _limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
            decision=AuthorizationDecision.DENY,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ):
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=_quota_limit(),
        )

    command = audit.record.call_args.args[0]

    assert (
        command.action
        is EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
    )
    assert (
        command.outcome
        is EnterpriseAdminAuditOutcome.DENIED
    )
    assert (
        command.failure_reason
        == "authorization_denied"
    )


def test_create_scope_mismatch_records_failure() -> None:
    service, _limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ):
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=_quota_limit(
                workspace_id="workspace_other",
            ),
        )

    command = audit.record.call_args.args[0]

    assert (
        command.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert command.failure_reason == "limit_scope_mismatch"


def test_create_repository_rejection_records_failure() -> None:
    service, limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )
    quota_limit = _quota_limit()
    limits.create(quota_limit)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=quota_limit,
        )

    command = audit.record.call_args.args[0]

    assert (
        command.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        command.failure_reason
        == "quota_limit_persistence_rejected"
    )


def test_list_repository_rejection_records_failure() -> None:
    service, _limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    with pytest.raises(
        ValueError,
        match="list limit",
    ):
        service.list_limits(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            dimension=(
                EnterpriseQuotaDimension.REWRITE_REQUESTS
            ),
            limit=0,
        )

    command = audit.record.call_args.args[0]

    assert (
        command.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        command.failure_reason
        == "quota_limit_query_rejected"
    )


def test_audit_failure_fails_read_closed() -> None:
    service, limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )
    quota_limit = _quota_limit()
    limits.create(quota_limit)

    audit.record.side_effect = RuntimeError(
        "audit unavailable"
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationAuditError,
        match="audit persistence failed",
    ):
        service.get_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit_id=quota_limit.quota_limit_id,
        )


def test_successful_create_is_reserved_for_f6c3b() -> None:
    service, _limits, audit = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    created = service.create_limit(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        quota_limit=_quota_limit(),
    )

    assert created.quota_limit_id == "limit_requests"
    audit.record.assert_not_called()
