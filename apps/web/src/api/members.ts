export type EnterpriseWorkspaceRole =
  | "owner"
  | "admin"
  | "editor"
  | "reviewer"
  | "viewer";

export type EnterpriseMembershipStatus =
  | "active"
  | "suspended"
  | "removed";

export interface EnterpriseWorkspaceMembership {
  membership_version: string;
  membership_id: string;
  organization_id: string;
  workspace_id: string;
  user_id: string;
  role: EnterpriseWorkspaceRole;
  status: EnterpriseMembershipStatus;
  created_at: string;
  updated_at: string;
}

export interface EnterpriseMember {
  membership: EnterpriseWorkspaceMembership;
  effective_permissions: string[];
}

export interface EnterpriseMemberList {
  workspace_id: string;
  members: EnterpriseMember[];
}

export interface EnterpriseOwnershipTransfer {
  previous_owner: EnterpriseWorkspaceMembership;
  new_owner: EnterpriseWorkspaceMembership;
}

export class EnterpriseMembershipApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "EnterpriseMembershipApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  signal?: AbortSignal;
}

interface ListEnterpriseMembersRequest
  extends RequestOptions {
  workspaceId: string;
  actorUserId: string;
  status?: EnterpriseMembershipStatus;
  limit?: number;
}

interface GetEnterpriseMemberRequest
  extends RequestOptions {
  workspaceId: string;
  actorUserId: string;
  userId: string;
}

interface AddEnterpriseMemberRequest
  extends RequestOptions {
  workspaceId: string;
  actorUserId: string;
  membershipId: string;
  userId: string;
  role: Exclude<
    EnterpriseWorkspaceRole,
    "owner"
  >;
}

interface ChangeEnterpriseMemberRoleRequest
  extends RequestOptions {
  workspaceId: string;
  actorUserId: string;
  userId: string;
  role: Exclude<
    EnterpriseWorkspaceRole,
    "owner"
  >;
}

interface EnterpriseMemberLifecycleRequest
  extends RequestOptions {
  workspaceId: string;
  actorUserId: string;
  userId: string;
}

interface TransferEnterpriseOwnershipRequest
  extends RequestOptions {
  workspaceId: string;
  actorUserId: string;
  targetUserId: string;
}

function isRecord(
  value: unknown
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null
  );
}

function isStringArray(
  value: unknown
): value is string[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) => typeof item === "string"
    )
  );
}

function isRole(
  value: unknown
): value is EnterpriseWorkspaceRole {
  return (
    value === "owner" ||
    value === "admin" ||
    value === "editor" ||
    value === "reviewer" ||
    value === "viewer"
  );
}

function isMembershipStatus(
  value: unknown
): value is EnterpriseMembershipStatus {
  return (
    value === "active" ||
    value === "suspended" ||
    value === "removed"
  );
}

function requireMembership(
  payload: unknown
): EnterpriseWorkspaceMembership {
  if (
    !isRecord(payload) ||
    typeof payload.membership_version !== "string" ||
    typeof payload.membership_id !== "string" ||
    typeof payload.organization_id !== "string" ||
    typeof payload.workspace_id !== "string" ||
    typeof payload.user_id !== "string" ||
    !isRole(payload.role) ||
    !isMembershipStatus(payload.status) ||
    typeof payload.created_at !== "string" ||
    typeof payload.updated_at !== "string"
  ) {
    throw new EnterpriseMembershipApiError(
      502,
      "invalid_membership_response"
    );
  }

  return payload as unknown as EnterpriseWorkspaceMembership;
}

function requireMember(
  payload: unknown
): EnterpriseMember {
  if (
    !isRecord(payload) ||
    !isStringArray(payload.effective_permissions)
  ) {
    throw new EnterpriseMembershipApiError(
      502,
      "invalid_member_response"
    );
  }

  return {
    membership: requireMembership(
      payload.membership
    ),
    effective_permissions:
      payload.effective_permissions
  };
}

function requireMemberList(
  payload: unknown
): EnterpriseMemberList {
  if (
    !isRecord(payload) ||
    typeof payload.workspace_id !== "string" ||
    !Array.isArray(payload.members)
  ) {
    throw new EnterpriseMembershipApiError(
      502,
      "invalid_member_list_response"
    );
  }

  return {
    workspace_id: payload.workspace_id,
    members: payload.members.map(
      (member) => requireMember(member)
    )
  };
}

function requireOwnershipTransfer(
  payload: unknown
): EnterpriseOwnershipTransfer {
  if (!isRecord(payload)) {
    throw new EnterpriseMembershipApiError(
      502,
      "invalid_ownership_transfer_response"
    );
  }

  return {
    previous_owner: requireMembership(
      payload.previous_owner
    ),
    new_owner: requireMembership(
      payload.new_owner
    )
  };
}

async function membershipErrorFromResponse(
  response: Response,
  fallback: string
): Promise<EnterpriseMembershipApiError> {
  let detail = fallback;

  try {
    const payload: unknown =
      await response.json();

    if (
      isRecord(payload) &&
      typeof payload.detail === "string"
    ) {
      detail = payload.detail;
    }
  } catch {
    // Preserve fallback.
  }

  return new EnterpriseMembershipApiError(
    response.status,
    detail
  );
}

async function requireJson(
  response: Response,
  fallback: string
): Promise<unknown> {
  if (!response.ok) {
    throw await membershipErrorFromResponse(
      response,
      fallback
    );
  }

  return response.json();
}

export async function listEnterpriseMembers({
  workspaceId,
  actorUserId,
  status,
  limit = 200,
  signal
}: ListEnterpriseMembersRequest): Promise<EnterpriseMemberList> {
  const query = new URLSearchParams({
    actor_user_id: actorUserId,
    limit: String(limit)
  });

  if (status !== undefined) {
    query.set(
      "status",
      status
    );
  }

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members?${query.toString()}`,
    {
      headers: {
        Accept: "application/json"
      },
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_list_http_${response.status}`
  );

  return requireMemberList(payload);
}

export async function getEnterpriseMember({
  workspaceId,
  actorUserId,
  userId,
  signal
}: GetEnterpriseMemberRequest): Promise<EnterpriseMember> {
  const query = new URLSearchParams({
    actor_user_id: actorUserId
  });

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members/${encodeURIComponent(
      userId
    )}?${query.toString()}`,
    {
      headers: {
        Accept: "application/json"
      },
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_get_http_${response.status}`
  );

  return requireMember(payload);
}

export async function addEnterpriseMember({
  workspaceId,
  actorUserId,
  membershipId,
  userId,
  role,
  signal
}: AddEnterpriseMemberRequest): Promise<EnterpriseMember> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId,
        membership_id: membershipId,
        user_id: userId,
        role
      }),
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_add_http_${response.status}`
  );

  return requireMember(payload);
}

export async function changeEnterpriseMemberRole({
  workspaceId,
  actorUserId,
  userId,
  role,
  signal
}: ChangeEnterpriseMemberRoleRequest): Promise<EnterpriseMember> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members/${encodeURIComponent(
      userId
    )}/role`,
    {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId,
        role
      }),
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_role_http_${response.status}`
  );

  return requireMember(payload);
}

export async function suspendEnterpriseMember({
  workspaceId,
  actorUserId,
  userId,
  signal
}: EnterpriseMemberLifecycleRequest): Promise<EnterpriseMember> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members/${encodeURIComponent(
      userId
    )}/suspend`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId
      }),
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_suspend_http_${response.status}`
  );

  return requireMember(payload);
}

export async function reactivateEnterpriseMember({
  workspaceId,
  actorUserId,
  userId,
  signal
}: EnterpriseMemberLifecycleRequest): Promise<EnterpriseMember> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members/${encodeURIComponent(
      userId
    )}/reactivate`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId
      }),
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_reactivate_http_${response.status}`
  );

  return requireMember(payload);
}

export async function removeEnterpriseMember({
  workspaceId,
  actorUserId,
  userId,
  signal
}: EnterpriseMemberLifecycleRequest): Promise<EnterpriseMember> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/members/${encodeURIComponent(
      userId
    )}`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId
      }),
      signal
    }
  );

  const payload = await requireJson(
    response,
    `member_remove_http_${response.status}`
  );

  return requireMember(payload);
}

export async function transferEnterpriseOwnership({
  workspaceId,
  actorUserId,
  targetUserId,
  signal
}: TransferEnterpriseOwnershipRequest): Promise<EnterpriseOwnershipTransfer> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/ownership-transfer`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId,
        target_user_id: targetUserId
      }),
      signal
    }
  );

  const payload = await requireJson(
    response,
    `ownership_transfer_http_${response.status}`
  );

  return requireOwnershipTransfer(payload);
}
