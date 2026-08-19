from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from app.v2.domain.enterprise_workspace import (
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.v2.domain.models import (
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)
from app.v2.repositories.interfaces import (
    UserRepository,
)
from app.v2.repositories.workspace_authority_provisioning import (
    AtomicWorkspaceAuthorityProvisioner,
)


class CanonicalWorkspaceProvisioningService:
    def __init__(
        self,
        *,
        users: UserRepository,
        provisioner: AtomicWorkspaceAuthorityProvisioner,
    ) -> None:
        self._users = users
        self._provisioner = provisioner

    def create_workspace(
        self,
        *,
        user_id: str,
        name: str,
    ) -> WorkspaceRecord:
        user = self._users.get(
            user_id
        )

        if user is None:
            raise ValueError(
                f"Unknown user: {user_id}"
            )

        now = datetime.now(UTC)

        workspace_id = (
            f"workspace_{uuid4().hex}"
        )

        organization_id = (
            self._compatibility_organization_id(
                workspace_id
            )
        )

        membership_id = (
            self._owner_membership_id(
                workspace_id=workspace_id,
                user_id=user_id,
            )
        )

        legacy_workspace = WorkspaceRecord(
            workspace_id=workspace_id,
            name=name,
            created_by_user_id=user_id,
            created_at=now,
        )

        legacy_membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            created_at=now,
        )

        enterprise_organization = (
            EnterpriseOrganization(
                organization_id=organization_id,
                name=f"{name} Organization",
                created_by_user_id=user_id,
                created_at=now,
            )
        )

        enterprise_workspace = (
            EnterpriseWorkspace(
                workspace_id=workspace_id,
                organization_id=organization_id,
                name=name,
                created_by_user_id=user_id,
                created_at=now,
                updated_at=now,
            )
        )

        enterprise_membership = (
            EnterpriseWorkspaceMembership(
                membership_id=membership_id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                user_id=user_id,
                role=EnterpriseWorkspaceRole.OWNER,
                created_at=now,
                updated_at=now,
            )
        )

        self._provisioner.provision(
            legacy_workspace=legacy_workspace,
            legacy_membership=legacy_membership,
            enterprise_organization=(
                enterprise_organization
            ),
            enterprise_workspace=(
                enterprise_workspace
            ),
            enterprise_membership=(
                enterprise_membership
            ),
        )

        return legacy_workspace

    @staticmethod
    def _compatibility_organization_id(
        workspace_id: str,
    ) -> str:
        digest = hashlib.sha256(
            (
                "workspace-compatibility-organization:"
                f"{workspace_id}"
            ).encode("utf-8")
        ).hexdigest()[:32]

        return f"org_{digest}"

    @staticmethod
    def _owner_membership_id(
        *,
        workspace_id: str,
        user_id: str,
    ) -> str:
        digest = hashlib.sha256(
            (
                "workspace-owner-membership:"
                f"{workspace_id}:{user_id}"
            ).encode("utf-8")
        ).hexdigest()[:32]

        return f"membership_{digest}"
