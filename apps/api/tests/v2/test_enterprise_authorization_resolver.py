from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
    EnterpriseWorkspaceStatus,
)
from app.v2.repositories.enterprise_workspace import (
    EnterpriseMembershipRepository,
    EnterpriseWorkspaceRepository,
    InMemoryEnterpriseMembershipRepository,
    InMemoryEnterpriseWorkspaceRepository,
    SQLiteEnterpriseMembershipRepository,
    SQLiteEnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    ENTERPRISE_AUTHORIZATION_RESOLUTION_VERSION,
    AuthorizationResolutionFailureReason,
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolutionResult,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
    AuthorizationDenialReason,
    EnterpriseAuthorizationService,
)

NOW = datetime(
    2026,
    8,
    13,
    8,
    0,
    tzinfo=UTC,
)


def _workspace(
    **updates: object,
) -> EnterpriseWorkspace:
    values: dict[str, object] = {
        "workspace_id": "workspace_test",
        "organization_id": "org_test",
        "name": "Enterprise Workspace",
        "created_by_user_id": "user_owner",
        "status": EnterpriseWorkspaceStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspace(**values)


def _membership(
    **updates: object,
) -> EnterpriseWorkspaceMembership:
    values: dict[str, object] = {
        "membership_id": "membership_test",
        "organization_id": "org_test",
        "workspace_id": "workspace_test",
        "user_id": "user_member",
        "role": EnterpriseWorkspaceRole.EDITOR,
        "status": EnterpriseMembershipStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspaceMembership(**values)


def _repositories(
    *,
    backend: str,
    database_path: Path,
) -> tuple[
    EnterpriseWorkspaceRepository,
    EnterpriseMembershipRepository,
]:
    if backend == "memory":
        return (
            InMemoryEnterpriseWorkspaceRepository(),
            InMemoryEnterpriseMembershipRepository(),
        )

    if backend == "sqlite":
        return (
            SQLiteEnterpriseWorkspaceRepository(
                database_path=database_path,
            ),
            SQLiteEnterpriseMembershipRepository(
                database_path=database_path,
            ),
        )

    raise AssertionError(f"unsupported test backend: {backend}")


def _resolver(
    *,
    workspaces: EnterpriseWorkspaceRepository,
    memberships: EnterpriseMembershipRepository,
) -> EnterpriseAuthorizationResolver:
    return EnterpriseAuthorizationResolver(
        workspaces=workspaces,
        memberships=memberships,
        authorization_service=EnterpriseAuthorizationService(),
    )


def test_resolution_version_is_frozen() -> None:
    assert ENTERPRISE_AUTHORIZATION_RESOLUTION_VERSION == "enterprise-authorization-resolution-v1"


def test_resolution_status_vocabulary_is_frozen() -> None:
    assert tuple(AuthorizationResolutionStatus) == (
        AuthorizationResolutionStatus.RESOLVED,
        AuthorizationResolutionStatus.RESOLUTION_FAILED,
    )


def test_resolution_failure_vocabulary_is_frozen() -> None:
    assert tuple(AuthorizationResolutionFailureReason) == (
        AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND,
        AuthorizationResolutionFailureReason.MEMBERSHIP_NOT_FOUND,
    )


def test_resolution_result_is_immutable() -> None:
    result = EnterpriseAuthorizationResolutionResult(
        status=(AuthorizationResolutionStatus.RESOLUTION_FAILED),
        workspace_id="workspace_test",
        user_id="user_test",
        permission=EnterprisePermission.WORKSPACE_READ,
        failure_reason=(AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND),
    )

    with pytest.raises(ValidationError):
        result.status = (  # type: ignore[misc]
            AuthorizationResolutionStatus.RESOLVED
        )


def test_resolution_result_forbids_extra_fields() -> None:
    result = EnterpriseAuthorizationResolutionResult(
        status=(AuthorizationResolutionStatus.RESOLUTION_FAILED),
        workspace_id="workspace_test",
        user_id="user_test",
        permission=EnterprisePermission.WORKSPACE_READ,
        failure_reason=(AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND),
    )

    with pytest.raises(ValidationError):
        EnterpriseAuthorizationResolutionResult.model_validate(
            {
                **result.model_dump(),
                "unexpected": True,
            }
        )


def test_resolved_result_requires_authorization() -> None:
    with pytest.raises(
        ValidationError,
        match="requires an authorization result",
    ):
        EnterpriseAuthorizationResolutionResult(
            status=AuthorizationResolutionStatus.RESOLVED,
            workspace_id="workspace_test",
            user_id="user_test",
            permission=EnterprisePermission.WORKSPACE_READ,
        )


def test_resolved_result_rejects_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot include a resolution failure reason",
    ):
        EnterpriseAuthorizationResolutionResult(
            status=AuthorizationResolutionStatus.RESOLVED,
            workspace_id="workspace_test",
            user_id="user_test",
            permission=EnterprisePermission.WORKSPACE_READ,
            failure_reason=(AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND),
            authorization=(
                EnterpriseAuthorizationService().authorize(
                    workspace=_workspace(),
                    membership=_membership(
                        user_id="user_test",
                    ),
                    user_id="user_test",
                    permission=(EnterprisePermission.WORKSPACE_READ),
                )
            ),
        )


def test_failed_result_requires_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a failure reason",
    ):
        EnterpriseAuthorizationResolutionResult(
            status=(AuthorizationResolutionStatus.RESOLUTION_FAILED),
            workspace_id="workspace_test",
            user_id="user_test",
            permission=EnterprisePermission.WORKSPACE_READ,
        )


def test_failed_result_rejects_authorization() -> None:
    authorization = EnterpriseAuthorizationService().authorize(
        workspace=_workspace(),
        membership=_membership(
            user_id="user_test",
        ),
        user_id="user_test",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    with pytest.raises(
        ValidationError,
        match="cannot include an authorization result",
    ):
        EnterpriseAuthorizationResolutionResult(
            status=(AuthorizationResolutionStatus.RESOLUTION_FAILED),
            workspace_id="workspace_test",
            user_id="user_test",
            permission=EnterprisePermission.WORKSPACE_READ,
            failure_reason=(AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND),
            authorization=authorization,
        )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_missing_workspace_is_resolution_failure(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_missing",
        user_id="user_member",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLUTION_FAILED
    assert result.failure_reason is AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND
    assert result.authorization is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_missing_membership_is_resolution_failure(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    workspaces.create(_workspace())

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_missing",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLUTION_FAILED
    assert result.failure_reason is AuthorizationResolutionFailureReason.MEMBERSHIP_NOT_FOUND
    assert result.authorization is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolved_records_flow_into_frozen_authorizer_allow(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())
    memberships.create(
        _membership(
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLVED
    assert result.failure_reason is None
    assert result.authorization is not None
    assert result.authorization.decision is AuthorizationDecision.ALLOW


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolved_records_flow_into_frozen_authorizer_deny(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())
    memberships.create(
        _membership(
            role=EnterpriseWorkspaceRole.VIEWER,
        )
    )

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLVED
    assert result.authorization is not None
    assert result.authorization.decision is AuthorizationDecision.DENY
    assert result.authorization.denial_reason is AuthorizationDenialReason.PERMISSION_NOT_GRANTED


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_suspended_workspace_is_authorization_denial_not_resolution_failure(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(
        _workspace(
            status=EnterpriseWorkspaceStatus.SUSPENDED,
        )
    )
    memberships.create(_membership())

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLVED
    assert result.failure_reason is None
    assert result.authorization is not None
    assert result.authorization.denial_reason is AuthorizationDenialReason.WORKSPACE_NOT_ACTIVE


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_removed_membership_is_authorization_denial_not_resolution_failure(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())
    memberships.create(
        _membership(
            status=EnterpriseMembershipStatus.REMOVED,
        )
    )

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLVED
    assert result.failure_reason is None
    assert result.authorization is not None
    assert result.authorization.denial_reason is AuthorizationDenialReason.MEMBERSHIP_NOT_ACTIVE


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolver_uses_current_membership_identity(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())

    memberships.create(
        _membership(
            membership_id="membership_old",
            role=EnterpriseWorkspaceRole.OWNER,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    memberships.create(
        _membership(
            membership_id="membership_current",
            role=EnterpriseWorkspaceRole.VIEWER,
            created_at=NOW + timedelta(hours=1),
            updated_at=NOW + timedelta(hours=1),
        )
    )

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.WORKSPACE_ARCHIVE,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLVED
    assert result.authorization is not None
    assert result.authorization.membership_id == "membership_current"
    assert result.authorization.role is EnterpriseWorkspaceRole.VIEWER
    assert result.authorization.denial_reason is AuthorizationDenialReason.PERMISSION_NOT_GRANTED


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_latest_removed_membership_remains_authoritative(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())

    memberships.create(
        _membership(
            membership_id="membership_active",
            role=EnterpriseWorkspaceRole.OWNER,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    memberships.create(
        _membership(
            membership_id="membership_removed",
            role=EnterpriseWorkspaceRole.OWNER,
            status=EnterpriseMembershipStatus.REMOVED,
            created_at=NOW + timedelta(hours=1),
            updated_at=NOW + timedelta(hours=1),
        )
    )

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.status is AuthorizationResolutionStatus.RESOLVED
    assert result.authorization is not None
    assert result.authorization.membership_id == "membership_removed"
    assert result.authorization.denial_reason is AuthorizationDenialReason.MEMBERSHIP_NOT_ACTIVE


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolution_preserves_requested_evidence(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())
    memberships.create(_membership())

    result = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    ).resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert result.resolution_version == ENTERPRISE_AUTHORIZATION_RESOLUTION_VERSION
    assert result.workspace_id == "workspace_test"
    assert result.user_id == "user_member"
    assert result.permission is EnterprisePermission.REWRITE_EXECUTE


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_resolution_is_deterministic(
    backend: str,
    tmp_path: Path,
) -> None:
    workspaces, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspaces.create(_workspace())
    memberships.create(_membership())

    resolver = _resolver(
        workspaces=workspaces,
        memberships=memberships,
    )

    first = resolver.resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )
    second = resolver.resolve(
        workspace_id="workspace_test",
        user_id="user_member",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert first == second
