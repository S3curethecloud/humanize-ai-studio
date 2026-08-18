from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

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
from app.v2.repositories.enterprise_admin_audit import (
    InMemoryEnterpriseAdminAuditRepository,
)
from app.v2.repositories.enterprise_quota_admin_mutations import (
    InMemoryEnterpriseQuotaAdminMutationRepository,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolutionResult,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
    EnterpriseAuthorizationResult,
)
from app.v2.services.enterprise_quota_admin_service import (
    EnterpriseQuotaAdminService,
)

WORKSPACE_ID = "workspace_test"
ACTOR_USER_ID = "user_admin"
FIXED_TIME = datetime(
    2026,
    8,
    16,
    7,
    0,
    tzinfo=UTC,
)


def _quota_limit() -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id="limit_requests",
        workspace_id=WORKSPACE_ID,
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


def _resolver() -> EnterpriseAuthorizationResolver:
    resolver = MagicMock(
        spec=EnterpriseAuthorizationResolver,
    )

    resolver.resolve.return_value = (
        EnterpriseAuthorizationResolutionResult(
            status=AuthorizationResolutionStatus.RESOLVED,
            workspace_id=WORKSPACE_ID,
            user_id=ACTOR_USER_ID,
            permission=EnterprisePermission.QUOTA_MANAGE,
            authorization=EnterpriseAuthorizationResult(
                decision=AuthorizationDecision.ALLOW,
                permission=EnterprisePermission.QUOTA_MANAGE,
                organization_id="organization_test",
                workspace_id=WORKSPACE_ID,
                membership_id="membership_test",
                user_id=ACTOR_USER_ID,
                role=EnterpriseWorkspaceRole.ADMIN,
            ),
        )
    )

    return resolver


def test_successful_create_atomically_persists_limit_and_success_audit() -> None:
    limits = InMemoryEnterpriseQuotaLimitRepository()
    audit = InMemoryEnterpriseAdminAuditRepository()

    recording = EnterpriseAdminAuditRecordingService(
        repository=audit,
        event_id_factory=lambda: "audit_create",
        clock=lambda: FIXED_TIME,
    )

    mutations = (
        InMemoryEnterpriseQuotaAdminMutationRepository(
            limits=limits,
            audit=audit,
        )
    )

    service = EnterpriseQuotaAdminService(
        limits=limits,
        authorization_resolver=_resolver(),
        audit_recording=recording,
        atomic_mutations=mutations,
    )

    quota_limit = _quota_limit()

    assert service.create_limit(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        quota_limit=quota_limit,
    ) == quota_limit

    assert (
        limits.get(quota_limit.quota_limit_id)
        == quota_limit
    )

    event = audit.get("audit_create")

    assert event is not None
    assert (
        event.action
        is EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
    )
    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.SUCCEEDED
    )
    assert event.workspace_id == WORKSPACE_ID
    assert event.actor_user_id == ACTOR_USER_ID
    assert event.target_type == "quota_limit"
    assert event.target_id == "limit_requests"
    assert event.occurred_at == FIXED_TIME
