export type ProviderCapability =
  | "rewrite"
  | "multi_candidate"
  | "long_document"
  | "claim_lock"
  | "voice_profile";

export interface ProviderCatalogTargetVisibility {
  target_id: string;
  provider_id: string;
  provider_display_name: string;
  model_id: string;
  capabilities: ProviderCapability[];
  enabled: boolean;
}

export interface WorkspaceProviderCatalogVisibility {
  workspace_id: string;
  catalog_scope: "platform";
  targets: ProviderCatalogTargetVisibility[];
}

export class WorkspaceProviderCatalogError
extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "WorkspaceProviderCatalogError";
    this.status = status;
    this.detail = detail;
  }
}

interface FetchWorkspaceProviderCatalogRequest {
  workspaceId: string;
  userId: string;
  enabledOnly?: boolean;
  limit?: number;
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

function isProviderCapability(
  value: unknown
): value is ProviderCapability {
  return (
    value === "rewrite" ||
    value === "multi_candidate" ||
    value === "long_document" ||
    value === "claim_lock" ||
    value === "voice_profile"
  );
}

function requireTarget(
  value: unknown
): ProviderCatalogTargetVisibility {
  if (
    !isRecord(value) ||
    typeof value.target_id !== "string" ||
    typeof value.provider_id !== "string" ||
    typeof value.provider_display_name !== "string" ||
    typeof value.model_id !== "string" ||
    !Array.isArray(value.capabilities) ||
    !value.capabilities.every(
      isProviderCapability
    ) ||
    typeof value.enabled !== "boolean"
  ) {
    throw new WorkspaceProviderCatalogError(
      502,
      "invalid_workspace_provider_catalog_response"
    );
  }

  return {
    target_id: value.target_id,
    provider_id: value.provider_id,
    provider_display_name:
      value.provider_display_name,
    model_id: value.model_id,
    capabilities: value.capabilities,
    enabled: value.enabled
  };
}

function requireCatalog(
  payload: unknown,
  {
    expectedWorkspaceId
  }: {
    expectedWorkspaceId: string;
  }
): WorkspaceProviderCatalogVisibility {
  if (
    !isRecord(payload) ||
    typeof payload.workspace_id !== "string" ||
    payload.workspace_id !== expectedWorkspaceId ||
    payload.catalog_scope !== "platform" ||
    !Array.isArray(payload.targets)
  ) {
    throw new WorkspaceProviderCatalogError(
      502,
      "invalid_workspace_provider_catalog_response"
    );
  }

  return {
    workspace_id: payload.workspace_id,
    catalog_scope: "platform",
    targets: payload.targets.map(
      requireTarget
    )
  };
}

export async function fetchWorkspaceProviderCatalog({
  workspaceId,
  userId,
  enabledOnly = false,
  limit = 1000,
  signal
}: FetchWorkspaceProviderCatalogRequest):
Promise<WorkspaceProviderCatalogVisibility> {
  const query = new URLSearchParams({
    user_id: userId,
    enabled_only: String(enabledOnly),
    limit: String(limit)
  });

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/providers?${query.toString()}`,
    {
      headers: {
        Accept: "application/json"
      },
      signal
    }
  );

  if (!response.ok) {
    let detail =
      `workspace_provider_catalog_http_${response.status}`;

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
      // Preserve status-derived detail.
    }

    throw new WorkspaceProviderCatalogError(
      response.status,
      detail
    );
  }

  const payload: unknown =
    await response.json();

  return requireCatalog(
    payload,
    {
      expectedWorkspaceId: workspaceId
    }
  );
}
