from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_rbac import (
    ENTERPRISE_RBAC_VERSION,
    ROLE_PERMISSION_MAP,
    EnterprisePermission,
    RolePermissionGrant,
    grant_for_role,
    permissions_for_role,
    role_has_permission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceRole,
)


def test_rbac_version_is_frozen() -> None:
    assert ENTERPRISE_RBAC_VERSION == "enterprise-rbac-v1"


def test_every_frozen_role_has_exactly_one_permission_set() -> None:
    assert set(ROLE_PERMISSION_MAP) == set(EnterpriseWorkspaceRole)


def test_owner_has_every_frozen_permission() -> None:
    assert permissions_for_role(EnterpriseWorkspaceRole.OWNER) == frozenset(EnterprisePermission)


def test_admin_does_not_receive_owner_only_permissions() -> None:
    admin = permissions_for_role(EnterpriseWorkspaceRole.ADMIN)

    assert EnterprisePermission.WORKSPACE_TRANSFER_OWNERSHIP not in admin
    assert EnterprisePermission.WORKSPACE_ARCHIVE not in admin


def test_owner_receives_owner_only_permissions() -> None:
    owner = permissions_for_role(EnterpriseWorkspaceRole.OWNER)

    assert EnterprisePermission.WORKSPACE_TRANSFER_OWNERSHIP in owner
    assert EnterprisePermission.WORKSPACE_ARCHIVE in owner


def test_editor_can_execute_rewrites_and_use_governed_controls() -> None:
    editor = permissions_for_role(EnterpriseWorkspaceRole.EDITOR)

    assert EnterprisePermission.REWRITE_EXECUTE in editor
    assert EnterprisePermission.VOICE_USE in editor
    assert EnterprisePermission.CLAIM_LOCK_USE in editor
    assert EnterprisePermission.PROVIDER_POLICY_USE in editor


def test_editor_cannot_manage_governed_controls() -> None:
    editor = permissions_for_role(EnterpriseWorkspaceRole.EDITOR)

    assert EnterprisePermission.VOICE_MANAGE not in editor
    assert EnterprisePermission.CLAIM_LOCK_MANAGE not in editor
    assert EnterprisePermission.PROVIDER_POLICY_MANAGE not in editor
    assert EnterprisePermission.QUOTA_MANAGE not in editor
    assert EnterprisePermission.SECURITY_MANAGE not in editor


def test_reviewer_can_review_approve_and_read_audit() -> None:
    reviewer = permissions_for_role(EnterpriseWorkspaceRole.REVIEWER)

    assert EnterprisePermission.DOCUMENTS_REVIEW in reviewer
    assert EnterprisePermission.DOCUMENTS_APPROVE in reviewer
    assert EnterprisePermission.AUDIT_READ in reviewer


def test_reviewer_cannot_execute_rewrites() -> None:
    reviewer = permissions_for_role(EnterpriseWorkspaceRole.REVIEWER)

    assert EnterprisePermission.REWRITE_EXECUTE not in reviewer


def test_reviewer_cannot_export_audit() -> None:
    reviewer = permissions_for_role(EnterpriseWorkspaceRole.REVIEWER)

    assert EnterprisePermission.AUDIT_EXPORT not in reviewer


def test_viewer_is_read_only() -> None:
    viewer = permissions_for_role(EnterpriseWorkspaceRole.VIEWER)

    assert EnterprisePermission.WORKSPACE_READ in viewer
    assert EnterprisePermission.REWRITE_READ in viewer
    assert EnterprisePermission.DOCUMENTS_READ in viewer
    assert EnterprisePermission.HISTORY_READ in viewer
    assert EnterprisePermission.VOICE_READ in viewer
    assert EnterprisePermission.CLAIM_LOCK_READ in viewer
    assert EnterprisePermission.ANALYTICS_READ in viewer

    forbidden = {
        EnterprisePermission.WORKSPACE_UPDATE,
        EnterprisePermission.MEMBERS_INVITE,
        EnterprisePermission.REWRITE_EXECUTE,
        EnterprisePermission.DOCUMENTS_CREATE,
        EnterprisePermission.DOCUMENTS_UPDATE,
        EnterprisePermission.DOCUMENTS_REVIEW,
        EnterprisePermission.DOCUMENTS_APPROVE,
        EnterprisePermission.DOCUMENTS_DELETE,
        EnterprisePermission.VOICE_USE,
        EnterprisePermission.VOICE_MANAGE,
        EnterprisePermission.CLAIM_LOCK_USE,
        EnterprisePermission.CLAIM_LOCK_MANAGE,
        EnterprisePermission.AUDIT_READ,
        EnterprisePermission.AUDIT_EXPORT,
        EnterprisePermission.QUOTA_MANAGE,
        EnterprisePermission.PROVIDER_POLICY_USE,
        EnterprisePermission.PROVIDER_POLICY_MANAGE,
        EnterprisePermission.EVALUATION_RUN,
        EnterprisePermission.EVALUATION_MANAGE,
        EnterprisePermission.INTEGRATIONS_MANAGE,
        EnterprisePermission.API_CREDENTIALS_MANAGE,
        EnterprisePermission.SECURITY_MANAGE,
    }

    assert viewer.isdisjoint(forbidden)


def test_admin_has_enterprise_administration_permissions() -> None:
    admin = permissions_for_role(EnterpriseWorkspaceRole.ADMIN)

    expected = {
        EnterprisePermission.MEMBERS_INVITE,
        EnterprisePermission.MEMBERS_ROLE_ASSIGN,
        EnterprisePermission.MEMBERS_REMOVE,
        EnterprisePermission.VOICE_MANAGE,
        EnterprisePermission.CLAIM_LOCK_MANAGE,
        EnterprisePermission.AUDIT_READ,
        EnterprisePermission.AUDIT_EXPORT,
        EnterprisePermission.QUOTA_MANAGE,
        EnterprisePermission.PROVIDER_POLICY_MANAGE,
        EnterprisePermission.EVALUATION_MANAGE,
        EnterprisePermission.INTEGRATIONS_MANAGE,
        EnterprisePermission.API_CREDENTIALS_MANAGE,
        EnterprisePermission.SECURITY_MANAGE,
    }

    assert expected.issubset(admin)


def test_use_permissions_do_not_imply_manage_permissions() -> None:
    editor = permissions_for_role(EnterpriseWorkspaceRole.EDITOR)

    pairs = (
        (
            EnterprisePermission.VOICE_USE,
            EnterprisePermission.VOICE_MANAGE,
        ),
        (
            EnterprisePermission.CLAIM_LOCK_USE,
            EnterprisePermission.CLAIM_LOCK_MANAGE,
        ),
        (
            EnterprisePermission.PROVIDER_POLICY_USE,
            EnterprisePermission.PROVIDER_POLICY_MANAGE,
        ),
    )

    for use_permission, manage_permission in pairs:
        assert use_permission in editor
        assert manage_permission not in editor


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    (
        (
            EnterpriseWorkspaceRole.OWNER,
            EnterprisePermission.WORKSPACE_TRANSFER_OWNERSHIP,
            True,
        ),
        (
            EnterpriseWorkspaceRole.ADMIN,
            EnterprisePermission.WORKSPACE_TRANSFER_OWNERSHIP,
            False,
        ),
        (
            EnterpriseWorkspaceRole.EDITOR,
            EnterprisePermission.REWRITE_EXECUTE,
            True,
        ),
        (
            EnterpriseWorkspaceRole.REVIEWER,
            EnterprisePermission.REWRITE_EXECUTE,
            False,
        ),
        (
            EnterpriseWorkspaceRole.VIEWER,
            EnterprisePermission.ANALYTICS_READ,
            True,
        ),
    ),
)
def test_role_has_permission_is_deterministic(
    role: EnterpriseWorkspaceRole,
    permission: EnterprisePermission,
    expected: bool,
) -> None:
    assert (
        role_has_permission(
            role,
            permission,
        )
        is expected
    )


def test_grant_for_role_matches_canonical_map() -> None:
    grant = grant_for_role(EnterpriseWorkspaceRole.ADMIN)

    assert grant.role is EnterpriseWorkspaceRole.ADMIN
    assert grant.permissions == permissions_for_role(EnterpriseWorkspaceRole.ADMIN)


def test_role_permission_grant_is_immutable() -> None:
    grant = grant_for_role(EnterpriseWorkspaceRole.VIEWER)

    with pytest.raises(ValidationError):
        grant.role = (  # type: ignore[misc]
            EnterpriseWorkspaceRole.ADMIN
        )


def test_role_permission_grant_forbids_extra_fields() -> None:
    grant = grant_for_role(EnterpriseWorkspaceRole.VIEWER)

    with pytest.raises(ValidationError):
        RolePermissionGrant.model_validate(
            {
                **grant.model_dump(),
                "unexpected": True,
            }
        )


def test_role_permission_map_is_not_mutable() -> None:
    with pytest.raises(TypeError):
        ROLE_PERMISSION_MAP[EnterpriseWorkspaceRole.VIEWER] = frozenset()  # type: ignore[index]


def test_builtin_role_permission_sets_are_monotonic_where_intended() -> None:
    viewer = permissions_for_role(EnterpriseWorkspaceRole.VIEWER)
    reviewer = permissions_for_role(EnterpriseWorkspaceRole.REVIEWER)
    editor = permissions_for_role(EnterpriseWorkspaceRole.EDITOR)
    admin = permissions_for_role(EnterpriseWorkspaceRole.ADMIN)
    owner = permissions_for_role(EnterpriseWorkspaceRole.OWNER)

    assert viewer < reviewer
    assert viewer < editor
    assert reviewer < admin
    assert editor < admin
    assert admin < owner


def test_future_facing_permission_namespaces_are_reserved() -> None:
    permissions = set(EnterprisePermission)

    expected = {
        EnterprisePermission.DOCUMENTS_APPROVE,
        EnterprisePermission.PROVIDER_POLICY_MANAGE,
        EnterprisePermission.EVALUATION_MANAGE,
        EnterprisePermission.INTEGRATIONS_MANAGE,
        EnterprisePermission.API_CREDENTIALS_MANAGE,
        EnterprisePermission.SECURITY_MANAGE,
    }

    assert expected.issubset(permissions)
