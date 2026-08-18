from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

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
from app.v2.repositories.enterprise_quota_admin_mutations import (
    EnterpriseQuotaAdminMutationRepository,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
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
    EnterpriseQuotaAdministrationError,
    EnterpriseQuotaAdminService,
    QuotaAdministrationFailureReason,
)

WORKSPACE_ID = "workspace_test"
ACTOR_USER_ID = "user_admin"


def _window() -> EnterpriseQuotaWindow:
    return EnterpriseQuotaWindow(
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
    )


def _quota_limit(
    *,
    quota_limit_id: str = "limit_requests",
    workspace_id: str = WORKSPACE_ID,
    dimension: EnterpriseQuotaDimension = (
        EnterpriseQuotaDimension.REWRITE_REQUESTS
    ),
) -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id=quota_limit_id,
        workspace_id=workspace_id,
        dimension=dimension,
        window=_window(),
        limit=100,
    )


def _authorization(
    *,
    permission: EnterprisePermission,
    decision: AuthorizationDecision = (
        AuthorizationDecision.ALLOW
    ),
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
            else AuthorizationDenialReason.PERMISSION_NOT_GRANTED
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
        authorization=_authorization(
            permission=permission,
            decision=decision,
        ),
    )


def _resolution_failed(
    *,
    permission: EnterprisePermission,
) -> EnterpriseAuthorizationResolutionResult:
    return EnterpriseAuthorizationResolutionResult(
        status=AuthorizationResolutionStatus.RESOLUTION_FAILED,
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

    authorization_resolver = MagicMock(
        spec=EnterpriseAuthorizationResolver,
    )
    authorization_resolver.resolve.return_value = resolution

    audit_recording = MagicMock(
        spec=EnterpriseAdminAuditRecordingService,
    )
    atomic_mutations = MagicMock(
        spec=EnterpriseQuotaAdminMutationRepository,
    )

    def create_limit_with_audit(
        *,
        quota_limit: EnterpriseWorkspaceQuotaLimit,
        audit_event: object,
    ) -> EnterpriseWorkspaceQuotaLimit:
        del audit_event
        return limits.create(quota_limit)

    atomic_mutations.create_limit_with_audit.side_effect = (
        create_limit_with_audit
    )

    service = EnterpriseQuotaAdminService(
        limits=limits,
        authorization_resolver=authorization_resolver,
        audit_recording=audit_recording,
        atomic_mutations=atomic_mutations,
    )

    return (
        service,
        limits,
        authorization_resolver,
    )


def test_create_limit_requires_quota_manage() -> None:
    service, _limits, resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    quota_limit = _quota_limit()

    assert (
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=quota_limit,
        )
        == quota_limit
    )

    resolver.resolve.assert_called_once_with(
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=EnterprisePermission.QUOTA_MANAGE,
    )


def test_create_limit_persists_authoritative_limit() -> None:
    service, limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    quota_limit = _quota_limit()

    service.create_limit(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        quota_limit=quota_limit,
    )

    assert limits.get(quota_limit.quota_limit_id) == quota_limit


def test_create_limit_rejects_workspace_scope_mismatch() -> None:
    service, limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ) as exc_info:
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=_quota_limit(
                workspace_id="workspace_other",
            ),
        )

    assert (
        exc_info.value.reason
        is QuotaAdministrationFailureReason.LIMIT_SCOPE_MISMATCH
    )
    assert limits.get("limit_requests") is None


def test_create_limit_propagates_repository_duplicate_failure() -> None:
    service, limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    quota_limit = _quota_limit()
    limits.create(quota_limit)

    with pytest.raises(
        ValueError,
        match="enterprise quota limit already exists",
    ):
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=quota_limit,
        )


def test_create_limit_propagates_repository_overlap_failure() -> None:
    service, limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_MANAGE,
        )
    )

    limits.create(
        _quota_limit(
            quota_limit_id="first",
        )
    )

    with pytest.raises(
        ValueError,
        match="enterprise quota limit overlaps existing authority",
    ):
        service.create_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit=_quota_limit(
                quota_limit_id="second",
            ),
        )


def test_get_limit_requires_quota_read() -> None:
    service, limits, resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    quota_limit = _quota_limit()
    limits.create(quota_limit)

    assert (
        service.get_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit_id=quota_limit.quota_limit_id,
        )
        == quota_limit
    )

    resolver.resolve.assert_called_once_with(
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=EnterprisePermission.QUOTA_READ,
    )


def test_get_limit_missing_fails() -> None:
    service, _limits, _resolver = _service(
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


def test_get_limit_never_returns_cross_workspace_limit() -> None:
    service, limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    limits.create(
        _quota_limit(
            workspace_id="workspace_other",
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ) as exc_info:
        service.get_limit(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            quota_limit_id="limit_requests",
        )

    assert (
        exc_info.value.reason
        is QuotaAdministrationFailureReason.LIMIT_NOT_FOUND
    )


def test_list_limits_requires_quota_read() -> None:
    service, limits, resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    quota_limit = _quota_limit()
    limits.create(quota_limit)

    assert service.list_limits(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
    ) == (quota_limit,)

    resolver.resolve.assert_called_once_with(
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=EnterprisePermission.QUOTA_READ,
    )


def test_list_limits_is_dimension_scoped() -> None:
    service, limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    requests = _quota_limit(
        quota_limit_id="requests",
    )
    input_characters = _quota_limit(
        quota_limit_id="input",
        dimension=EnterpriseQuotaDimension.INPUT_CHARACTERS,
    )

    limits.create(requests)
    limits.create(input_characters)

    assert service.list_limits(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
    ) == (requests,)


def test_list_limits_propagates_repository_list_validation() -> None:
    service, _limits, _resolver = _service(
        resolution=_resolved(
            permission=EnterprisePermission.QUOTA_READ,
        )
    )

    with pytest.raises(
        ValueError,
        match="enterprise quota limit list limit",
    ):
        service.list_limits(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            limit=0,
        )


@pytest.mark.parametrize(
    "permission",
    [
        EnterprisePermission.QUOTA_READ,
        EnterprisePermission.QUOTA_MANAGE,
    ],
)
def test_authorization_resolution_failure_fails_closed(
    permission: EnterprisePermission,
) -> None:
    service, _limits, _resolver = _service(
        resolution=_resolution_failed(
            permission=permission,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ) as exc_info:
        if permission is EnterprisePermission.QUOTA_MANAGE:
            service.create_limit(
                actor_user_id=ACTOR_USER_ID,
                workspace_id=WORKSPACE_ID,
                quota_limit=_quota_limit(),
            )
        else:
            service.get_limit(
                actor_user_id=ACTOR_USER_ID,
                workspace_id=WORKSPACE_ID,
                quota_limit_id="missing",
            )

    assert (
        exc_info.value.reason
        is QuotaAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED
    )


@pytest.mark.parametrize(
    "permission",
    [
        EnterprisePermission.QUOTA_READ,
        EnterprisePermission.QUOTA_MANAGE,
    ],
)
def test_authorization_denial_fails_closed(
    permission: EnterprisePermission,
) -> None:
    service, _limits, _resolver = _service(
        resolution=_resolved(
            permission=permission,
            decision=AuthorizationDecision.DENY,
        )
    )

    with pytest.raises(
        EnterpriseQuotaAdministrationError
    ) as exc_info:
        if permission is EnterprisePermission.QUOTA_MANAGE:
            service.create_limit(
                actor_user_id=ACTOR_USER_ID,
                workspace_id=WORKSPACE_ID,
                quota_limit=_quota_limit(),
            )
        else:
            service.get_limit(
                actor_user_id=ACTOR_USER_ID,
                workspace_id=WORKSPACE_ID,
                quota_limit_id="missing",
            )

    assert (
        exc_info.value.reason
        is QuotaAdministrationFailureReason.AUTHORIZATION_DENIED
    )
