from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceRole,
)

ENTERPRISE_RBAC_VERSION: Literal["enterprise-rbac-v1"] = "enterprise-rbac-v1"


class EnterprisePermission(StrEnum):
    # Workspace lifecycle and configuration.
    WORKSPACE_READ = "workspace.read"
    WORKSPACE_UPDATE = "workspace.update"
    WORKSPACE_ARCHIVE = "workspace.archive"
    WORKSPACE_TRANSFER_OWNERSHIP = "workspace.transfer_ownership"

    # Membership and role administration.
    MEMBERS_READ = "members.read"
    MEMBERS_INVITE = "members.invite"
    MEMBERS_ROLE_ASSIGN = "members.role_assign"
    MEMBERS_REMOVE = "members.remove"

    # Rewrite execution and completed rewrite access.
    REWRITE_EXECUTE = "rewrite.execute"
    REWRITE_READ = "rewrite.read"

    # Versioned-document authority reserved for the
    # enterprise document lifecycle.
    DOCUMENTS_READ = "documents.read"
    DOCUMENTS_CREATE = "documents.create"
    DOCUMENTS_UPDATE = "documents.update"
    DOCUMENTS_REVIEW = "documents.review"
    DOCUMENTS_APPROVE = "documents.approve"
    DOCUMENTS_DELETE = "documents.delete"

    # Existing rewrite-history authority.
    HISTORY_READ = "history.read"

    # Voice DNA.
    VOICE_READ = "voice.read"
    VOICE_USE = "voice.use"
    VOICE_MANAGE = "voice.manage"

    # Claim Lock / protected terminology.
    CLAIM_LOCK_READ = "claim_lock.read"
    CLAIM_LOCK_USE = "claim_lock.use"
    CLAIM_LOCK_MANAGE = "claim_lock.manage"

    # Persistent analytics.
    ANALYTICS_READ = "analytics.read"

    # Enterprise governance evidence.
    AUDIT_READ = "audit.read"
    AUDIT_EXPORT = "audit.export"

    # Workspace quota controls.
    QUOTA_READ = "quota.read"
    QUOTA_MANAGE = "quota.manage"

    # V2.8+ provider-routing policy.
    PROVIDER_POLICY_READ = "provider_policy.read"
    PROVIDER_POLICY_USE = "provider_policy.use"
    PROVIDER_POLICY_MANAGE = "provider_policy.manage"

    # V2.8+ evaluation / EvalOps.
    EVALUATION_READ = "evaluation.read"
    EVALUATION_RUN = "evaluation.run"
    EVALUATION_MANAGE = "evaluation.manage"

    # V3+ enterprise integrations.
    INTEGRATIONS_READ = "integrations.read"
    INTEGRATIONS_MANAGE = "integrations.manage"

    # V3+ machine/API access.
    API_CREDENTIALS_READ = "api_credentials.read"
    API_CREDENTIALS_MANAGE = "api_credentials.manage"

    # V3+ SSO, SCIM, security policy, and related
    # enterprise security configuration.
    SECURITY_READ = "security.read"
    SECURITY_MANAGE = "security.manage"


class RolePermissionGrant(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    rbac_version: Literal["enterprise-rbac-v1"] = ENTERPRISE_RBAC_VERSION

    role: EnterpriseWorkspaceRole
    permissions: frozenset[EnterprisePermission]


_VIEWER_PERMISSIONS = frozenset(
    {
        EnterprisePermission.WORKSPACE_READ,
        EnterprisePermission.MEMBERS_READ,
        EnterprisePermission.REWRITE_READ,
        EnterprisePermission.DOCUMENTS_READ,
        EnterprisePermission.HISTORY_READ,
        EnterprisePermission.VOICE_READ,
        EnterprisePermission.CLAIM_LOCK_READ,
        EnterprisePermission.ANALYTICS_READ,
        EnterprisePermission.QUOTA_READ,
        EnterprisePermission.PROVIDER_POLICY_READ,
        EnterprisePermission.EVALUATION_READ,
    }
)

_REVIEWER_PERMISSIONS = frozenset(
    {
        *_VIEWER_PERMISSIONS,
        EnterprisePermission.DOCUMENTS_REVIEW,
        EnterprisePermission.DOCUMENTS_APPROVE,
        EnterprisePermission.AUDIT_READ,
    }
)

_EDITOR_PERMISSIONS = frozenset(
    {
        *_VIEWER_PERMISSIONS,
        EnterprisePermission.REWRITE_EXECUTE,
        EnterprisePermission.DOCUMENTS_CREATE,
        EnterprisePermission.DOCUMENTS_UPDATE,
        EnterprisePermission.VOICE_USE,
        EnterprisePermission.CLAIM_LOCK_USE,
        EnterprisePermission.PROVIDER_POLICY_USE,
        EnterprisePermission.EVALUATION_RUN,
    }
)

_ADMIN_PERMISSIONS = frozenset(
    {
        *_EDITOR_PERMISSIONS,
        *_REVIEWER_PERMISSIONS,
        EnterprisePermission.WORKSPACE_UPDATE,
        EnterprisePermission.MEMBERS_INVITE,
        EnterprisePermission.MEMBERS_ROLE_ASSIGN,
        EnterprisePermission.MEMBERS_REMOVE,
        EnterprisePermission.DOCUMENTS_DELETE,
        EnterprisePermission.VOICE_MANAGE,
        EnterprisePermission.CLAIM_LOCK_MANAGE,
        EnterprisePermission.AUDIT_EXPORT,
        EnterprisePermission.QUOTA_MANAGE,
        EnterprisePermission.PROVIDER_POLICY_MANAGE,
        EnterprisePermission.EVALUATION_MANAGE,
        EnterprisePermission.INTEGRATIONS_READ,
        EnterprisePermission.INTEGRATIONS_MANAGE,
        EnterprisePermission.API_CREDENTIALS_READ,
        EnterprisePermission.API_CREDENTIALS_MANAGE,
        EnterprisePermission.SECURITY_READ,
        EnterprisePermission.SECURITY_MANAGE,
    }
)

_OWNER_PERMISSIONS = frozenset(
    {
        *EnterprisePermission,
    }
)


_ROLE_PERMISSION_MAP: dict[
    EnterpriseWorkspaceRole,
    frozenset[EnterprisePermission],
] = {
    EnterpriseWorkspaceRole.OWNER: _OWNER_PERMISSIONS,
    EnterpriseWorkspaceRole.ADMIN: _ADMIN_PERMISSIONS,
    EnterpriseWorkspaceRole.EDITOR: _EDITOR_PERMISSIONS,
    EnterpriseWorkspaceRole.REVIEWER: _REVIEWER_PERMISSIONS,
    EnterpriseWorkspaceRole.VIEWER: _VIEWER_PERMISSIONS,
}


ROLE_PERMISSION_MAP: Mapping[
    EnterpriseWorkspaceRole,
    frozenset[EnterprisePermission],
] = MappingProxyType(_ROLE_PERMISSION_MAP)


def permissions_for_role(
    role: EnterpriseWorkspaceRole,
) -> frozenset[EnterprisePermission]:
    return ROLE_PERMISSION_MAP[role]


def role_has_permission(
    role: EnterpriseWorkspaceRole,
    permission: EnterprisePermission,
) -> bool:
    return permission in permissions_for_role(role)


def grant_for_role(
    role: EnterpriseWorkspaceRole,
) -> RolePermissionGrant:
    return RolePermissionGrant(
        role=role,
        permissions=permissions_for_role(role),
    )
