from __future__ import annotations

from datetime import UTC, datetime

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
from app.v2.services.enterprise_authorization_service import (
    ENTERPRISE_AUTHORIZATION_VERSION,
    AuthorizationDecision,
    AuthorizationDenialReason,
    EnterpriseAuthorizationResult,
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
        "user_id": "user_owner",
        "role": EnterpriseWorkspaceRole.OWNER,
        "status": EnterpriseMembershipStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspaceMembership(**values)


def _service() -> EnterpriseAuthorizationService:
    return EnterpriseAuthorizationService()


def test_authorization_version_is_frozen() -> None:
    assert ENTERPRISE_AUTHORIZATION_VERSION == "enterprise-authorization-v1"


def test_decision_vocabulary_is_frozen() -> None:
    assert tuple(AuthorizationDecision) == (
        AuthorizationDecision.ALLOW,
        AuthorizationDecision.DENY,
    )


def test_denial_reason_vocabulary_is_frozen() -> None:
    assert tuple(AuthorizationDenialReason) == (
        AuthorizationDenialReason.WORKSPACE_NOT_ACTIVE,
        AuthorizationDenialReason.MEMBERSHIP_NOT_ACTIVE,
        AuthorizationDenialReason.SCOPE_MISMATCH,
        AuthorizationDenialReason.PERMISSION_NOT_GRANTED,
    )


def test_authorization_result_is_immutable() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    with pytest.raises(ValidationError):
        result.decision = (  # type: ignore[misc]
            AuthorizationDecision.DENY
        )


def test_authorization_result_forbids_extra_fields() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    with pytest.raises(ValidationError):
        EnterpriseAuthorizationResult.model_validate(
            {
                **result.model_dump(),
                "unexpected": True,
            }
        )


def test_allow_result_cannot_include_denial_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="allowed authorization cannot include",
    ):
        EnterpriseAuthorizationResult(
            decision=AuthorizationDecision.ALLOW,
            permission=EnterprisePermission.WORKSPACE_READ,
            organization_id="org_test",
            workspace_id="workspace_test",
            membership_id="membership_test",
            user_id="user_owner",
            role=EnterpriseWorkspaceRole.OWNER,
            denial_reason=(AuthorizationDenialReason.PERMISSION_NOT_GRANTED),
        )


def test_deny_result_requires_denial_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="denied authorization requires",
    ):
        EnterpriseAuthorizationResult(
            decision=AuthorizationDecision.DENY,
            permission=EnterprisePermission.WORKSPACE_READ,
            organization_id="org_test",
            workspace_id="workspace_test",
            membership_id="membership_test",
            user_id="user_owner",
            role=EnterpriseWorkspaceRole.OWNER,
        )


def test_owner_is_allowed_owner_only_permission() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            role=EnterpriseWorkspaceRole.OWNER,
        ),
        user_id="user_owner",
        permission=(EnterprisePermission.WORKSPACE_TRANSFER_OWNERSHIP),
    )

    assert result.decision is AuthorizationDecision.ALLOW
    assert result.denial_reason is None


def test_admin_is_denied_owner_only_permission() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            role=EnterpriseWorkspaceRole.ADMIN,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_ARCHIVE,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.PERMISSION_NOT_GRANTED


def test_editor_is_allowed_rewrite_execution() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            role=EnterpriseWorkspaceRole.EDITOR,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert result.decision is AuthorizationDecision.ALLOW


def test_reviewer_is_denied_rewrite_execution() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            role=EnterpriseWorkspaceRole.REVIEWER,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.PERMISSION_NOT_GRANTED


def test_viewer_is_allowed_analytics_read() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            role=EnterpriseWorkspaceRole.VIEWER,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.ANALYTICS_READ,
    )

    assert result.decision is AuthorizationDecision.ALLOW


@pytest.mark.parametrize(
    "status",
    (
        EnterpriseWorkspaceStatus.SUSPENDED,
        EnterpriseWorkspaceStatus.ARCHIVED,
    ),
)
def test_non_active_workspace_denies_even_owner(
    status: EnterpriseWorkspaceStatus,
) -> None:
    result = _service().authorize(
        workspace=_workspace(
            status=status,
        ),
        membership=_membership(
            role=EnterpriseWorkspaceRole.OWNER,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.WORKSPACE_NOT_ACTIVE


@pytest.mark.parametrize(
    "status",
    (
        EnterpriseMembershipStatus.SUSPENDED,
        EnterpriseMembershipStatus.REMOVED,
    ),
)
def test_non_active_membership_denies_even_owner(
    status: EnterpriseMembershipStatus,
) -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            status=status,
            role=EnterpriseWorkspaceRole.OWNER,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.MEMBERSHIP_NOT_ACTIVE


def test_organization_scope_mismatch_denies() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            organization_id="org_other",
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.SCOPE_MISMATCH


def test_workspace_scope_mismatch_denies() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            workspace_id="workspace_other",
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.SCOPE_MISMATCH


def test_user_scope_mismatch_denies() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            user_id="user_alice",
        ),
        user_id="user_bob",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.denial_reason is AuthorizationDenialReason.SCOPE_MISMATCH


def test_workspace_lifecycle_precedes_membership_lifecycle() -> None:
    result = _service().authorize(
        workspace=_workspace(
            status=EnterpriseWorkspaceStatus.SUSPENDED,
        ),
        membership=_membership(
            status=EnterpriseMembershipStatus.SUSPENDED,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.denial_reason is AuthorizationDenialReason.WORKSPACE_NOT_ACTIVE


def test_membership_lifecycle_precedes_scope_evaluation() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            status=EnterpriseMembershipStatus.REMOVED,
            organization_id="org_other",
        ),
        user_id="user_other",
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    assert result.denial_reason is AuthorizationDenialReason.MEMBERSHIP_NOT_ACTIVE


def test_scope_evaluation_precedes_permission_evaluation() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            workspace_id="workspace_other",
            role=EnterpriseWorkspaceRole.VIEWER,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.WORKSPACE_ARCHIVE,
    )

    assert result.denial_reason is AuthorizationDenialReason.SCOPE_MISMATCH


def test_denial_is_returned_not_raised() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            role=EnterpriseWorkspaceRole.VIEWER,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert isinstance(
        result,
        EnterpriseAuthorizationResult,
    )
    assert result.decision is AuthorizationDecision.DENY


def test_authorization_is_deterministic() -> None:
    service = _service()
    workspace = _workspace()
    membership = _membership(
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    first = service.authorize(
        workspace=workspace,
        membership=membership,
        user_id="user_owner",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )
    second = service.authorize(
        workspace=workspace,
        membership=membership,
        user_id="user_owner",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert first == second


def test_result_carries_authorization_evidence() -> None:
    result = _service().authorize(
        workspace=_workspace(),
        membership=_membership(
            membership_id="membership_editor",
            role=EnterpriseWorkspaceRole.EDITOR,
        ),
        user_id="user_owner",
        permission=EnterprisePermission.REWRITE_EXECUTE,
    )

    assert result.authorization_version == ENTERPRISE_AUTHORIZATION_VERSION
    assert result.organization_id == "org_test"
    assert result.workspace_id == "workspace_test"
    assert result.membership_id == "membership_editor"
    assert result.user_id == "user_owner"
    assert result.role is EnterpriseWorkspaceRole.EDITOR
    assert result.permission is EnterprisePermission.REWRITE_EXECUTE
