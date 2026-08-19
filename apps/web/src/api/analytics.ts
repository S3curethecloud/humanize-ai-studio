export type AnalyticsOperation =
  | "single_rewrite"
  | "multi_candidate_rewrite"
  | "long_document_rewrite";

export interface AnalyticsOperationBucket {
  operation: AnalyticsOperation;
  event_count: number;
  succeeded_count: number;
  controlled_failure_count: number;
  system_failure_count: number;
}

export interface WorkspaceAnalyticsSnapshot {
  analytics_version: "workspace-analytics-v1";
  workspace_id: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  event_count: number;
  succeeded_count: number;
  controlled_failure_count: number;
  system_failure_count: number;
  total_duration_ms: number;
  total_input_char_count: number;
  total_output_char_count: number;
  total_provider_executions: number;
  total_fallbacks: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  operations: AnalyticsOperationBucket[];
}

export class WorkspaceAnalyticsError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "WorkspaceAnalyticsError";
    this.status = status;
    this.detail = detail;
  }
}

interface FetchWorkspaceAnalyticsRequest {
  workspaceId: string;
  userId: string;
  periodStart: Date;
  periodEnd: Date;
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

function isNumber(
  value: unknown
): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value)
  );
}

function isOperation(
  value: unknown
): value is AnalyticsOperation {
  return (
    value === "single_rewrite" ||
    value === "multi_candidate_rewrite" ||
    value === "long_document_rewrite"
  );
}

function requireOperationBucket(
  value: unknown
): AnalyticsOperationBucket {
  if (
    !isRecord(value) ||
    !isOperation(value.operation) ||
    !isNumber(value.event_count) ||
    !isNumber(value.succeeded_count) ||
    !isNumber(value.controlled_failure_count) ||
    !isNumber(value.system_failure_count)
  ) {
    throw new WorkspaceAnalyticsError(
      502,
      "invalid_workspace_analytics_response"
    );
  }

  return value as unknown as AnalyticsOperationBucket;
}

function requireWorkspaceAnalyticsSnapshot(
  payload: unknown
): WorkspaceAnalyticsSnapshot {
  if (
    !isRecord(payload) ||
    payload.analytics_version !==
      "workspace-analytics-v1" ||
    typeof payload.workspace_id !== "string" ||
    typeof payload.period_start !== "string" ||
    typeof payload.period_end !== "string" ||
    typeof payload.generated_at !== "string" ||
    !isNumber(payload.event_count) ||
    !isNumber(payload.succeeded_count) ||
    !isNumber(payload.controlled_failure_count) ||
    !isNumber(payload.system_failure_count) ||
    !isNumber(payload.total_duration_ms) ||
    !isNumber(payload.total_input_char_count) ||
    !isNumber(payload.total_output_char_count) ||
    !isNumber(payload.total_provider_executions) ||
    !isNumber(payload.total_fallbacks) ||
    !isNumber(payload.total_input_tokens) ||
    !isNumber(payload.total_output_tokens) ||
    !isNumber(payload.total_tokens) ||
    !Array.isArray(payload.operations)
  ) {
    throw new WorkspaceAnalyticsError(
      502,
      "invalid_workspace_analytics_response"
    );
  }

  const operations =
    payload.operations.map(requireOperationBucket);

  return {
    ...payload,
    operations
  } as WorkspaceAnalyticsSnapshot;
}

export async function fetchWorkspaceAnalytics({
  workspaceId,
  userId,
  periodStart,
  periodEnd,
  signal
}: FetchWorkspaceAnalyticsRequest):
Promise<WorkspaceAnalyticsSnapshot> {
  const query = new URLSearchParams({
    user_id: userId,
    period_start: periodStart.toISOString(),
    period_end: periodEnd.toISOString()
  });

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/analytics?${query.toString()}`,
    {
      headers: {
        Accept: "application/json"
      },
      signal
    }
  );

  if (!response.ok) {
    let detail =
      `workspace_analytics_http_${response.status}`;

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

    throw new WorkspaceAnalyticsError(
      response.status,
      detail
    );
  }

  const payload: unknown =
    await response.json();

  return requireWorkspaceAnalyticsSnapshot(
    payload
  );
}
