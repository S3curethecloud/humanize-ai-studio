export type EnterpriseQuotaDimension =
  | "rewrite_requests"
  | "input_characters"
  | "output_characters"
  | "candidates_generated"
  | "long_document_sections";

export interface EnterpriseQuotaWindow {
  window_start: string;
  window_end: string;
}

export interface EnterpriseQuotaLimit {
  limit_version: string;
  quota_limit_id: string;
  workspace_id: string;
  dimension: EnterpriseQuotaDimension;
  window: EnterpriseQuotaWindow;
  limit: number;
}

async function errorFromResponse(
  response: Response,
  fallback: string
): Promise<Error> {
  try {
    const body = (await response.json()) as {
      detail?: unknown;
    };

    if (typeof body.detail === "string") {
      return new Error(body.detail);
    }
  } catch {
    // Preserve fallback.
  }

  return new Error(fallback);
}

export async function listQuotaLimits(
  workspaceId: string,
  actorUserId: string,
  dimension: EnterpriseQuotaDimension
): Promise<EnterpriseQuotaLimit[]> {
  const query = new URLSearchParams({
    actor_user_id: actorUserId,
    dimension,
    limit: "100"
  });

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/quota-limits?${query.toString()}`
  );

  if (!response.ok) {
    throw await errorFromResponse(
      response,
      `Quota list failed with status ${response.status}.`
    );
  }

  const payload = (await response.json()) as {
    quota_limits: EnterpriseQuotaLimit[];
  };

  return payload.quota_limits;
}

export async function createQuotaLimit(
  workspaceId: string,
  actorUserId: string,
  input: {
    quotaLimitId: string;
    dimension: EnterpriseQuotaDimension;
    windowStart: string;
    windowEnd: string;
    limit: number;
  }
): Promise<EnterpriseQuotaLimit> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/quota-limits`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        actor_user_id: actorUserId,
        quota_limit_id: input.quotaLimitId,
        dimension: input.dimension,
        window: {
          window_start: input.windowStart,
          window_end: input.windowEnd
        },
        limit: input.limit
      })
    }
  );

  if (!response.ok) {
    throw await errorFromResponse(
      response,
      `Quota creation failed with status ${response.status}.`
    );
  }

  const payload = (await response.json()) as {
    quota_limit: EnterpriseQuotaLimit;
  };

  return payload.quota_limit;
}
