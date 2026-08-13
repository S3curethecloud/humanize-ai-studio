from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.v2.repositories.enterprise_workspace import (
    EnterpriseMembershipRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
)


class MembershipAdministrationFailureReason(StrEnum):
    AUTHORIZATION_RESOLUTION_FAILED = "authorization_resolution_failed"
    AUTHORIZATION_DENIED = "authorization_denied"
    TARGET_NOT_FOUND = "target_not_found"
    DUPLICATE_CURRENT_MEMBERSHIP = "duplicate_current_membership"
    NEW_MEMBERSHIP_ID_REQUIRED = "new_membership_id_required"
    OWNER_ROLE_REQUIRES_TRANSFER = "owner_role_requires_transfer"
    OWNER_LIFECYCLE_PROTECTED = "owner_lifecycle_protected"
    MEMBERSHIP_REMOVED = "membership_removed"
    MEMBERSHIP_NOT_ACTIVE = "membership_not_active"
    MEMBERSHIP_NOT_SUSPENDED = "membership_not_suspended"
    TARGET_SCOPE_MISMATCH = "target_scope_mismatch"
    TRANSACTION_REQUIRED = "transaction_required"


class EnterpriseMembershipAdministrationError(RuntimeError):
    def __init__(
        self,
        reason: MembershipAdministrationFailureReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason.value)


class EnterpriseMembershipAdminService:
    def __init__(
        self,
        *,
        memberships: EnterpriseMembershipRepository,
        authorization_resolver: EnterpriseAuthorizationResolver,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._memberships = memberships
        self._authorization_resolver = authorization_resolver
        self._now = now or (lambda: datetime.now(UTC))

    def add_member(
        self,
        *,
        actor_user_id: str,
        organization_id: str,
        workspace_id: str,
        membership_id: str,
        user_id: str,
        role: EnterpriseWorkspaceRole,
    ) -> EnterpriseWorkspaceMembership:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.MEMBERS_INVITE,
        )

        if role is EnterpriseWorkspaceRole.OWNER:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER
            )

        current = self._memberships.get_current(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        if current is not None:
            if current.status is not EnterpriseMembershipStatus.REMOVED:
                raise EnterpriseMembershipAdministrationError(
                    MembershipAdministrationFailureReason.DUPLICATE_CURRENT_MEMBERSHIP
                )

            if membership_id == current.membership_id:
                raise EnterpriseMembershipAdministrationError(
                    MembershipAdministrationFailureReason.NEW_MEMBERSHIP_ID_REQUIRED
                )

        now = self._now()

        membership = EnterpriseWorkspaceMembership(
            membership_id=membership_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status=EnterpriseMembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        return self._memberships.create(membership)

    def get_member(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        user_id: str,
    ) -> EnterpriseWorkspaceMembership:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.MEMBERS_READ,
        )

        membership = self._memberships.get_current(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        if membership is None:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.TARGET_NOT_FOUND
            )

        return membership

    def list_members(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        status: EnterpriseMembershipStatus | None = None,
        limit: int = 200,
    ) -> tuple[EnterpriseWorkspaceMembership, ...]:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.MEMBERS_READ,
        )

        return self._memberships.list_for_workspace(
            workspace_id=workspace_id,
            status=status,
            limit=limit,
        )

    def change_role(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        target_user_id: str,
        role: EnterpriseWorkspaceRole,
    ) -> EnterpriseWorkspaceMembership:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=(EnterprisePermission.MEMBERS_ROLE_ASSIGN),
        )

        membership = self._require_target(
            workspace_id=workspace_id,
            user_id=target_user_id,
        )

        if membership.status is EnterpriseMembershipStatus.REMOVED:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED
            )

        if (
            membership.role is EnterpriseWorkspaceRole.OWNER
            or role is EnterpriseWorkspaceRole.OWNER
        ):
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER
            )

        updated = membership.model_copy(
            update={
                "role": role,
                "updated_at": self._now(),
            }
        )

        return self._memberships.update(updated)

    def suspend_member(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        target_user_id: str,
    ) -> EnterpriseWorkspaceMembership:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.MEMBERS_REMOVE,
        )

        membership = self._require_target(
            workspace_id=workspace_id,
            user_id=target_user_id,
        )

        self._require_non_owner(membership)

        if membership.status is not EnterpriseMembershipStatus.ACTIVE:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.MEMBERSHIP_NOT_ACTIVE
            )

        updated = membership.model_copy(
            update={
                "status": (EnterpriseMembershipStatus.SUSPENDED),
                "updated_at": self._now(),
            }
        )

        return self._memberships.update(updated)

    def reactivate_member(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        target_user_id: str,
    ) -> EnterpriseWorkspaceMembership:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.MEMBERS_REMOVE,
        )

        membership = self._require_target(
            workspace_id=workspace_id,
            user_id=target_user_id,
        )

        self._require_non_owner(membership)

        if membership.status is EnterpriseMembershipStatus.REMOVED:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED
            )

        if membership.status is not EnterpriseMembershipStatus.SUSPENDED:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.MEMBERSHIP_NOT_SUSPENDED
            )

        updated = membership.model_copy(
            update={
                "status": EnterpriseMembershipStatus.ACTIVE,
                "updated_at": self._now(),
            }
        )

        return self._memberships.update(updated)

    def remove_member(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        target_user_id: str,
    ) -> EnterpriseWorkspaceMembership:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.MEMBERS_REMOVE,
        )

        membership = self._require_target(
            workspace_id=workspace_id,
            user_id=target_user_id,
        )

        self._require_non_owner(membership)

        if membership.status is EnterpriseMembershipStatus.REMOVED:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED
            )

        updated = membership.model_copy(
            update={
                "status": EnterpriseMembershipStatus.REMOVED,
                "updated_at": self._now(),
            }
        )

        return self._memberships.update(updated)

    def transfer_ownership(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        target_user_id: str,
    ) -> tuple[
        EnterpriseWorkspaceMembership,
        EnterpriseWorkspaceMembership,
    ]:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=(EnterprisePermission.WORKSPACE_TRANSFER_OWNERSHIP),
        )

        actor = self._require_target(
            workspace_id=workspace_id,
            user_id=actor_user_id,
        )
        target = self._require_target(
            workspace_id=workspace_id,
            user_id=target_user_id,
        )

        if (
            actor.role is not EnterpriseWorkspaceRole.OWNER
            or actor.status is not EnterpriseMembershipStatus.ACTIVE
        ):
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.OWNER_LIFECYCLE_PROTECTED
            )

        if target.status is not EnterpriseMembershipStatus.ACTIVE:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.MEMBERSHIP_NOT_ACTIVE
            )

        if (
            actor.organization_id != target.organization_id
            or actor.workspace_id != target.workspace_id
            or actor.workspace_id != workspace_id
        ):
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.TARGET_SCOPE_MISMATCH
            )

        if target.role is EnterpriseWorkspaceRole.OWNER:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER
            )

        now = self._now()

        previous_owner = actor.model_copy(
            update={
                "role": EnterpriseWorkspaceRole.ADMIN,
                "updated_at": now,
            }
        )
        new_owner = target.model_copy(
            update={
                "role": EnterpriseWorkspaceRole.OWNER,
                "updated_at": now,
            }
        )

        updated = self._memberships.update_many_atomic(
            (
                previous_owner,
                new_owner,
            )
        )

        if len(updated) != 2:
            raise RuntimeError("ownership transfer repository returned an invalid atomic result")

        return (
            updated[0],
            updated[1],
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

        if resolution.status is not AuthorizationResolutionStatus.RESOLVED:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED
            )

        authorization = resolution.authorization

        if authorization is None or authorization.decision is not AuthorizationDecision.ALLOW:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.AUTHORIZATION_DENIED
            )

    def _require_target(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> EnterpriseWorkspaceMembership:
        membership = self._memberships.get_current(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        if membership is None:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.TARGET_NOT_FOUND
            )

        return membership

    @staticmethod
    def _require_non_owner(
        membership: EnterpriseWorkspaceMembership,
    ) -> None:
        if membership.role is EnterpriseWorkspaceRole.OWNER:
            raise EnterpriseMembershipAdministrationError(
                MembershipAdministrationFailureReason.OWNER_LIFECYCLE_PROTECTED
            )
