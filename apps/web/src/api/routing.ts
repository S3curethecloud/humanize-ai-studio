import type {
  ProviderCapability
} from "./providers";

export type RoutingOperationKind =
  | "single_rewrite"
  | "multi_candidate_rewrite"
  | "long_document_rewrite";

export type RoutingOperationStatus =
  | "open"
  | "succeeded"
  | "failed"
  | "no_provider_execution";

export type RoutingEvidenceBindingStatus =
  | "reserved"
  | "recorded";

export type RoutingEvidenceExecutionOutcome =
  | "not_executed"
  | "succeeded"
  | "failed";

export interface EnterpriseProviderRoutingEvidenceBinding {
  ordinal: number;
  evidence_id: string;
  status: RoutingEvidenceBindingStatus;
}

export interface RoutingEvidenceRecordVisibility {
  evidence_id: string;
  policy: Record<string, unknown>;
  decision: Record<string, unknown>;
  execution_outcome:
    RoutingEvidenceExecutionOutcome;
  executed_target_id: string | null;
  execution_fallback_used: boolean;
  attempts: unknown[];
  observed_at: string;
}

export interface EnterpriseWorkspaceProviderRoutingOperationVisibility {
  operation_id: string;
  workspace_id: string;
  user_id: string;
  operation_kind: RoutingOperationKind;
  policy_id: string;
  policy_revision: number;
  required_capabilities: ProviderCapability[];
  routing_evidence_bindings:
    EnterpriseProviderRoutingEvidenceBinding[];
  status: RoutingOperationStatus;
  rewrite_history_id: string | null;
  long_document_audit_id: string | null;
  failure_code: string | null;
  created_at: string;
  updated_at: string;
  revision: number;
}

export interface WorkspaceProviderRoutingEvidenceBindingVisibility {
  binding: EnterpriseProviderRoutingEvidenceBinding;
  routing_evidence:
    RoutingEvidenceRecordVisibility | null;
}

export interface WorkspaceProviderRoutingExecutionEvidenceVisibility {
  operation:
    EnterpriseWorkspaceProviderRoutingOperationVisibility;
  bindings:
    WorkspaceProviderRoutingEvidenceBindingVisibility[];
}

export interface WorkspaceProviderRoutingExecutionEvidenceList {
  workspace_id: string;
  records:
    WorkspaceProviderRoutingExecutionEvidenceVisibility[];
}

export class WorkspaceRoutingExecutionError
extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "WorkspaceRoutingExecutionError";
    this.status = status;
    this.detail = detail;
  }
}

interface FetchWorkspaceRoutingExecutionsRequest {
  workspaceId: string;
  userId: string;
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

function isPositiveInteger(
  value: unknown
): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 1
  );
}

function isNullableString(
  value: unknown
): value is string | null {
  return (
    typeof value === "string" ||
    value === null
  );
}

function isRoutingOperationKind(
  value: unknown
): value is RoutingOperationKind {
  return (
    value === "single_rewrite" ||
    value === "multi_candidate_rewrite" ||
    value === "long_document_rewrite"
  );
}

function isRoutingOperationStatus(
  value: unknown
): value is RoutingOperationStatus {
  return (
    value === "open" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "no_provider_execution"
  );
}

function isBindingStatus(
  value: unknown
): value is RoutingEvidenceBindingStatus {
  return (
    value === "reserved" ||
    value === "recorded"
  );
}

function isExecutionOutcome(
  value: unknown
): value is RoutingEvidenceExecutionOutcome {
  return (
    value === "not_executed" ||
    value === "succeeded" ||
    value === "failed"
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

function invalidResponse():
WorkspaceRoutingExecutionError {
  return new WorkspaceRoutingExecutionError(
    502,
    "invalid_workspace_routing_execution_response"
  );
}

function requireBinding(
  value: unknown
): EnterpriseProviderRoutingEvidenceBinding {
  if (
    !isRecord(value) ||
    !isPositiveInteger(value.ordinal) ||
    typeof value.evidence_id !== "string" ||
    !isBindingStatus(value.status)
  ) {
    throw invalidResponse();
  }

  return {
    ordinal: value.ordinal,
    evidence_id: value.evidence_id,
    status: value.status
  };
}

function requireRoutingEvidence(
  value: unknown
): RoutingEvidenceRecordVisibility {
  if (
    !isRecord(value) ||
    typeof value.evidence_id !== "string" ||
    !isRecord(value.policy) ||
    !isRecord(value.decision) ||
    !isExecutionOutcome(
      value.execution_outcome
    ) ||
    !isNullableString(
      value.executed_target_id
    ) ||
    typeof value.execution_fallback_used !==
      "boolean" ||
    !Array.isArray(value.attempts) ||
    typeof value.observed_at !== "string"
  ) {
    throw invalidResponse();
  }

  return {
    evidence_id: value.evidence_id,
    policy: value.policy,
    decision: value.decision,
    execution_outcome:
      value.execution_outcome,
    executed_target_id:
      value.executed_target_id,
    execution_fallback_used:
      value.execution_fallback_used,
    attempts: value.attempts,
    observed_at: value.observed_at
  };
}

function requireOperation(
  value: unknown
): EnterpriseWorkspaceProviderRoutingOperationVisibility {
  if (
    !isRecord(value) ||
    typeof value.operation_id !== "string" ||
    typeof value.workspace_id !== "string" ||
    typeof value.user_id !== "string" ||
    !isRoutingOperationKind(
      value.operation_kind
    ) ||
    typeof value.policy_id !== "string" ||
    !isPositiveInteger(
      value.policy_revision
    ) ||
    !Array.isArray(
      value.required_capabilities
    ) ||
    !value.required_capabilities.every(
      isProviderCapability
    ) ||
    !Array.isArray(
      value.routing_evidence_bindings
    ) ||
    !isRoutingOperationStatus(
      value.status
    ) ||
    !isNullableString(
      value.rewrite_history_id
    ) ||
    !isNullableString(
      value.long_document_audit_id
    ) ||
    !isNullableString(
      value.failure_code
    ) ||
    typeof value.created_at !== "string" ||
    typeof value.updated_at !== "string" ||
    !isPositiveInteger(
      value.revision
    )
  ) {
    throw invalidResponse();
  }

  const routingEvidenceBindings =
    value.routing_evidence_bindings.map(
      requireBinding
    );

  return {
    operation_id: value.operation_id,
    workspace_id: value.workspace_id,
    user_id: value.user_id,
    operation_kind: value.operation_kind,
    policy_id: value.policy_id,
    policy_revision: value.policy_revision,
    required_capabilities:
      value.required_capabilities,
    routing_evidence_bindings:
      routingEvidenceBindings,
    status: value.status,
    rewrite_history_id:
      value.rewrite_history_id,
    long_document_audit_id:
      value.long_document_audit_id,
    failure_code: value.failure_code,
    created_at: value.created_at,
    updated_at: value.updated_at,
    revision: value.revision
  };
}

function requireBindingView(
  value: unknown
): WorkspaceProviderRoutingEvidenceBindingVisibility {
  if (
    !isRecord(value)
  ) {
    throw invalidResponse();
  }

  const binding = requireBinding(
    value.binding
  );

  if (
    binding.status === "reserved"
  ) {
    if (
      value.routing_evidence !== null
    ) {
      throw invalidResponse();
    }

    return {
      binding,
      routing_evidence: null
    };
  }

  if (
    value.routing_evidence === null
  ) {
    throw invalidResponse();
  }

  const routingEvidence =
    requireRoutingEvidence(
      value.routing_evidence
    );

  if (
    routingEvidence.evidence_id !==
    binding.evidence_id
  ) {
    throw invalidResponse();
  }

  return {
    binding,
    routing_evidence: routingEvidence
  };
}

function requireExecutionRecord(
  value: unknown
): WorkspaceProviderRoutingExecutionEvidenceVisibility {
  if (
    !isRecord(value) ||
    !Array.isArray(value.bindings)
  ) {
    throw invalidResponse();
  }

  const operation =
    requireOperation(
      value.operation
    );

  const bindings =
    value.bindings.map(
      requireBindingView
    );

  if (
    bindings.length !==
    operation.routing_evidence_bindings.length
  ) {
    throw invalidResponse();
  }

  for (
    let index = 0;
    index < bindings.length;
    index += 1
  ) {
    const view =
      bindings[index];

    const operationBinding =
      operation
        .routing_evidence_bindings[index];

    if (
      view.binding.ordinal !==
        operationBinding.ordinal ||
      view.binding.evidence_id !==
        operationBinding.evidence_id ||
      view.binding.status !==
        operationBinding.status
    ) {
      throw invalidResponse();
    }
  }

  return {
    operation,
    bindings
  };
}

function requireList(
  payload: unknown,
  {
    expectedWorkspaceId
  }: {
    expectedWorkspaceId: string;
  }
): WorkspaceProviderRoutingExecutionEvidenceList {
  if (
    !isRecord(payload) ||
    typeof payload.workspace_id !== "string" ||
    payload.workspace_id !==
      expectedWorkspaceId ||
    !Array.isArray(payload.records)
  ) {
    throw invalidResponse();
  }

  const records =
    payload.records.map(
      requireExecutionRecord
    );

  if (
    records.some(
      (record) =>
        record.operation.workspace_id !==
        expectedWorkspaceId
    )
  ) {
    throw invalidResponse();
  }

  return {
    workspace_id: payload.workspace_id,
    records
  };
}

export async function fetchWorkspaceRoutingExecutions({
  workspaceId,
  userId,
  limit = 50,
  signal
}: FetchWorkspaceRoutingExecutionsRequest):
Promise<WorkspaceProviderRoutingExecutionEvidenceList> {
  const query = new URLSearchParams({
    user_id: userId,
    limit: String(limit)
  });

  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/routing-executions?${query.toString()}`,
    {
      headers: {
        Accept: "application/json"
      },
      signal
    }
  );

  if (!response.ok) {
    let detail =
      `workspace_routing_execution_http_${response.status}`;

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

    throw new WorkspaceRoutingExecutionError(
      response.status,
      detail
    );
  }

  const payload: unknown =
    await response.json();

  return requireList(
    payload,
    {
      expectedWorkspaceId: workspaceId
    }
  );
}
