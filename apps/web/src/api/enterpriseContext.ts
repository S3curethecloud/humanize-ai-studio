export interface EnterpriseWorkspaceAccessContext {
  workspace: {
    workspace_version: string;
    workspace_id: string;
    organization_id: string;
    name: string;
    created_by_user_id: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  membership: {
    membership_version: string;
    membership_id: string;
    organization_id: string;
    workspace_id: string;
    user_id: string;
    role: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  permissions: string[];
}

export class EnterpriseAccessContextError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "EnterpriseAccessContextError";
    this.status = status;
    this.detail = detail;
  }
}

interface AccessContextRequest {
  workspaceId: string;
  userId: string;
  signal?: AbortSignal;
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

function requireAccessContext(
  payload: unknown
): EnterpriseWorkspaceAccessContext {
  if (!isRecord(payload)) {
    throw new EnterpriseAccessContextError(
      502,
      "invalid_access_context_response"
    );
  }

  const workspace = payload.workspace;
  const membership = payload.membership;
  const permissions = payload.permissions;

  if (
    !isRecord(workspace) ||
    typeof workspace.workspace_id !== "string" ||
    typeof workspace.name !== "string" ||
    !isRecord(membership) ||
    typeof membership.membership_id !== "string" ||
    typeof membership.workspace_id !== "string" ||
    typeof membership.user_id !== "string" ||
    typeof membership.role !== "string" ||
    !isStringArray(permissions)
  ) {
    throw new EnterpriseAccessContextError(
      502,
      "invalid_access_context_response"
    );
  }

  return payload as unknown as EnterpriseWorkspaceAccessContext;
}

export async function fetchEnterpriseAccessContext({
  workspaceId,
  userId,
  signal
}: AccessContextRequest): Promise<EnterpriseWorkspaceAccessContext> {
  const query = new URLSearchParams({
    user_id: userId
  });

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/access-context?${query.toString()}`,
    {
      headers: {
        Accept: "application/json"
      },
      signal
    }
  );

  if (!response.ok) {
    let detail =
      `access_context_http_${response.status}`;

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
      // Preserve the status-derived error detail.
    }

    throw new EnterpriseAccessContextError(
      response.status,
      detail
    );
  }

  const payload: unknown =
    await response.json();

  return requireAccessContext(payload);
}
