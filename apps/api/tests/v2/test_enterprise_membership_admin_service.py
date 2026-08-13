from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
    EnterpriseWorkspaceStatus,
)
from app.v2.repositories.enterprise_workspace import (
    InMemoryEnterpriseMembershipRepository,
    InMemoryEnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    EnterpriseAuthorizationService,
)
from app.v2.services.enterprise_membership_admin_service import (
    EnterpriseMembershipAdministrationError,
    EnterpriseMembershipAdminService,
    MembershipAdministrationFailureReason,
)

NOW = datetime(
    2026,
    8,
    13,
    8,
    0,
    tzinfo=UTC,
)
LATER = NOW + timedelta(minutes=1)


def _workspace() -> EnterpriseWorkspace:
    return EnterpriseWorkspace(
        workspace_id="workspace_test",
        organization_id="org_test",
        name="Enterprise Workspace",
        created_by_user_id="user_owner",
        status=EnterpriseWorkspaceStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


def _membership(
    *,
    membership_id: str,
    user_id: str,
    role: EnterpriseWorkspaceRole,
    status: EnterpriseMembershipStatus = (EnterpriseMembershipStatus.ACTIVE),
    created_at: datetime = NOW,
) -> EnterpriseWorkspaceMembership:
    return EnterpriseWorkspaceMembership(
        membership_id=membership_id,
        organization_id="org_test",
        workspace_id="workspace_test",
        user_id=user_id,
        role=role,
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


def _service(
    *,
    actor_role: EnterpriseWorkspaceRole = (EnterpriseWorkspaceRole.OWNER),
) -> tuple[
    EnterpriseMembershipAdminService,
    InMemoryEnterpriseMembershipRepository,
]:
    workspaces = InMemoryEnterpriseWorkspaceRepository()
    memberships = InMemoryEnterpriseMembershipRepository()

    workspaces.create(_workspace())
    memberships.create(
        _membership(
            membership_id="membership_actor",
            user_id="user_actor",
            role=actor_role,
        )
    )

    resolver = EnterpriseAuthorizationResolver(
        workspaces=workspaces,
        memberships=memberships,
        authorization_service=(EnterpriseAuthorizationService()),
    )

    service = EnterpriseMembershipAdminService(
        memberships=memberships,
        authorization_resolver=resolver,
        now=lambda: LATER,
    )

    return service, memberships


def _assert_reason(
    exc_info: pytest.ExceptionInfo[EnterpriseMembershipAdministrationError],
    reason: MembershipAdministrationFailureReason,
) -> None:
    assert exc_info.value.reason is reason


def test_owner_can_add_non_owner_member() -> None:
    service, memberships = _service()

    created = service.add_member(
        actor_user_id="user_actor",
        organization_id="org_test",
        workspace_id="workspace_test",
        membership_id="membership_editor",
        user_id="user_editor",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    assert created.role is EnterpriseWorkspaceRole.EDITOR
    assert created.status is EnterpriseMembershipStatus.ACTIVE
    assert (
        memberships.get_current(
            workspace_id="workspace_test",
            user_id="user_editor",
        )
        == created
    )


def test_admin_can_add_non_owner_member() -> None:
    service, _ = _service(actor_role=EnterpriseWorkspaceRole.ADMIN)

    created = service.add_member(
        actor_user_id="user_actor",
        organization_id="org_test",
        workspace_id="workspace_test",
        membership_id="membership_viewer",
        user_id="user_viewer",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    assert created.role is EnterpriseWorkspaceRole.VIEWER


def test_editor_cannot_add_member() -> None:
    service, _ = _service(actor_role=EnterpriseWorkspaceRole.EDITOR)

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.add_member(
            actor_user_id="user_actor",
            organization_id="org_test",
            workspace_id="workspace_test",
            membership_id="membership_viewer",
            user_id="user_viewer",
            role=EnterpriseWorkspaceRole.VIEWER,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.AUTHORIZATION_DENIED,
    )


def test_add_member_cannot_create_owner() -> None:
    service, _ = _service()

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.add_member(
            actor_user_id="user_actor",
            organization_id="org_test",
            workspace_id="workspace_test",
            membership_id="membership_owner",
            user_id="user_other",
            role=EnterpriseWorkspaceRole.OWNER,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER,
    )


def test_duplicate_current_membership_is_rejected() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_existing",
            user_id="user_member",
            role=EnterpriseWorkspaceRole.VIEWER,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.add_member(
            actor_user_id="user_actor",
            organization_id="org_test",
            workspace_id="workspace_test",
            membership_id="membership_new",
            user_id="user_member",
            role=EnterpriseWorkspaceRole.EDITOR,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.DUPLICATE_CURRENT_MEMBERSHIP,
    )


def test_removed_member_rejoin_requires_new_identity() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_old",
            user_id="user_member",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.REMOVED,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.add_member(
            actor_user_id="user_actor",
            organization_id="org_test",
            workspace_id="workspace_test",
            membership_id="membership_old",
            user_id="user_member",
            role=EnterpriseWorkspaceRole.EDITOR,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.NEW_MEMBERSHIP_ID_REQUIRED,
    )


def test_removed_member_can_rejoin_with_new_identity() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_old",
            user_id="user_member",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.REMOVED,
        )
    )

    created = service.add_member(
        actor_user_id="user_actor",
        organization_id="org_test",
        workspace_id="workspace_test",
        membership_id="membership_new",
        user_id="user_member",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    assert created.membership_id == "membership_new"
    assert memberships.get_by_id("membership_old") is not None


def test_admin_can_change_non_owner_role() -> None:
    service, memberships = _service(actor_role=EnterpriseWorkspaceRole.ADMIN)

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    updated = service.change_role(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
        target_user_id="user_target",
        role=EnterpriseWorkspaceRole.REVIEWER,
    )

    assert updated.role is EnterpriseWorkspaceRole.REVIEWER
    assert updated.updated_at == LATER


def test_change_role_cannot_promote_to_owner() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.ADMIN,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.change_role(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
            role=EnterpriseWorkspaceRole.OWNER,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER,
    )


def test_change_role_cannot_demote_owner() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_owner_2",
            user_id="user_owner_2",
            role=EnterpriseWorkspaceRole.OWNER,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.change_role(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_owner_2",
            role=EnterpriseWorkspaceRole.ADMIN,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER,
    )


def test_removed_membership_cannot_change_role() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
            status=EnterpriseMembershipStatus.REMOVED,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.change_role(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
            role=EnterpriseWorkspaceRole.REVIEWER,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED,
    )


def test_admin_can_suspend_active_non_owner() -> None:
    service, memberships = _service(actor_role=EnterpriseWorkspaceRole.ADMIN)

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    updated = service.suspend_member(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
        target_user_id="user_target",
    )

    assert updated.status is EnterpriseMembershipStatus.SUSPENDED


def test_owner_cannot_be_suspended() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_owner_2",
            user_id="user_owner_2",
            role=EnterpriseWorkspaceRole.OWNER,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.suspend_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_owner_2",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.OWNER_LIFECYCLE_PROTECTED,
    )


def test_suspend_requires_active_membership() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.SUSPENDED,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.suspend_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_NOT_ACTIVE,
    )


def test_suspended_member_can_be_reactivated() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.SUSPENDED,
        )
    )

    updated = service.reactivate_member(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
        target_user_id="user_target",
    )

    assert updated.status is EnterpriseMembershipStatus.ACTIVE


def test_removed_member_cannot_be_reactivated() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.REMOVED,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.reactivate_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED,
    )


def test_active_member_cannot_be_reactivated() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.reactivate_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_NOT_SUSPENDED,
    )


def test_active_non_owner_can_be_removed() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
        )
    )

    updated = service.remove_member(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
        target_user_id="user_target",
    )

    assert updated.status is EnterpriseMembershipStatus.REMOVED
    assert memberships.get_by_id("membership_target") == updated


def test_suspended_non_owner_can_be_removed() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.SUSPENDED,
        )
    )

    updated = service.remove_member(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
        target_user_id="user_target",
    )

    assert updated.status is EnterpriseMembershipStatus.REMOVED


def test_owner_cannot_be_removed() -> None:
    service, _ = _service()

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.remove_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_actor",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.OWNER_LIFECYCLE_PROTECTED,
    )


def test_removed_membership_cannot_be_removed_again() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.VIEWER,
            status=EnterpriseMembershipStatus.REMOVED,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.remove_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED,
    )


def test_target_lookup_is_current_membership_only() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_old",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
            created_at=NOW,
        )
    )
    memberships.create(
        _membership(
            membership_id="membership_removed",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
            status=EnterpriseMembershipStatus.REMOVED,
            created_at=NOW + timedelta(seconds=1),
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.change_role(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
            role=EnterpriseWorkspaceRole.REVIEWER,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED,
    )


def test_get_member_requires_members_read() -> None:
    service, memberships = _service(actor_role=EnterpriseWorkspaceRole.VIEWER)

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    assert (
        service.get_member(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            user_id="user_target",
        ).membership_id
        == "membership_target"
    )


def test_list_members_requires_members_read() -> None:
    service, memberships = _service(actor_role=EnterpriseWorkspaceRole.VIEWER)

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    listed = service.list_members(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
    )

    assert {membership.user_id for membership in listed} == {
        "user_actor",
        "user_target",
    }


def test_missing_actor_fails_resolution() -> None:
    service, _ = _service()

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.list_members(
            actor_user_id="user_missing",
            workspace_id="workspace_test",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED,
    )


def test_missing_target_is_rejected() -> None:
    service, _ = _service()

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.change_role(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_missing",
            role=EnterpriseWorkspaceRole.VIEWER,
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.TARGET_NOT_FOUND,
    )


def test_actor_and_target_are_separate_principals() -> None:
    service, memberships = _service(actor_role=EnterpriseWorkspaceRole.ADMIN)

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    updated = service.change_role(
        actor_user_id="user_actor",
        workspace_id="workspace_test",
        target_user_id="user_target",
        role=EnterpriseWorkspaceRole.REVIEWER,
    )

    assert updated.user_id == "user_target"
    actor_membership = memberships.get_current(
        workspace_id="workspace_test",
        user_id="user_actor",
    )
    assert actor_membership is not None
    assert actor_membership.role is EnterpriseWorkspaceRole.ADMIN


def test_ownership_transfer_requires_transactional_boundary() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.ADMIN,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.transfer_ownership(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.TRANSACTION_REQUIRED,
    )

    actor_membership = memberships.get_current(
        workspace_id="workspace_test",
        user_id="user_actor",
    )
    target_membership = memberships.get_current(
        workspace_id="workspace_test",
        user_id="user_target",
    )

    assert actor_membership is not None
    assert target_membership is not None
    assert actor_membership.role is EnterpriseWorkspaceRole.OWNER
    assert target_membership.role is EnterpriseWorkspaceRole.ADMIN


def test_non_owner_cannot_reach_transfer_transaction_gate() -> None:
    service, memberships = _service(actor_role=EnterpriseWorkspaceRole.ADMIN)

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.EDITOR,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.transfer_ownership(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.AUTHORIZATION_DENIED,
    )


def test_suspended_transfer_target_is_rejected_before_transaction_gate() -> None:
    service, memberships = _service()

    memberships.create(
        _membership(
            membership_id="membership_target",
            user_id="user_target",
            role=EnterpriseWorkspaceRole.ADMIN,
            status=EnterpriseMembershipStatus.SUSPENDED,
        )
    )

    with pytest.raises(EnterpriseMembershipAdministrationError) as exc_info:
        service.transfer_ownership(
            actor_user_id="user_actor",
            workspace_id="workspace_test",
            target_user_id="user_target",
        )

    _assert_reason(
        exc_info,
        MembershipAdministrationFailureReason.MEMBERSHIP_NOT_ACTIVE,
    )
