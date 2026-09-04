export type EvalOpsVersion =
  "eval-ops-v1";

export type EvaluationMetric =
  | "claim_preservation"
  | "naturalness"
  | "rewrite_distance"
  | "latency_ms"
  | "provider_error_rate";

export type EvaluationComparator =
  | "at_least"
  | "at_most";

export type EvaluationRunOutcome =
  | "succeeded"
  | "failed";

export type EvaluationGateDecision =
  | "passed"
  | "failed";

export type EnterpriseEvaluationOperationStatus =
  | "open"
  | "succeeded"
  | "failed";

export type EnterpriseEvaluationEvidenceKind =
  | "run"
  | "gate";

export interface EvaluationDatasetIdentity {
  eval_version: EvalOpsVersion;
  dataset_id: string;
  dataset_version: string;
}

export interface EvaluationRunIdentity {
  eval_version: EvalOpsVersion;
  run_id: string;
  dataset: EvaluationDatasetIdentity;
  target_id: string;
}

export interface EvaluationMetricResult {
  metric: EvaluationMetric;
  value: number;
}

export interface EvaluationRunRecord {
  eval_version: EvalOpsVersion;
  identity: EvaluationRunIdentity;
  outcome: EvaluationRunOutcome;
  evaluated_case_count: number;
  failed_case_count: number;
  metric_results: EvaluationMetricResult[];
  failure_reason: string | null;
}

export interface EvaluationThreshold {
  metric: EvaluationMetric;
  comparator: EvaluationComparator;
  threshold: number;
}

export interface EvaluationQualityGate {
  eval_version: EvalOpsVersion;
  gate_id: string;
  thresholds: EvaluationThreshold[];
}

export interface EvaluationGateResult {
  eval_version: EvalOpsVersion;
  gate: EvaluationQualityGate;
  run_id: string;
  decision: EvaluationGateDecision;
  metric_results: EvaluationMetricResult[];
}

export interface WorkspaceEvaluationEvidenceRecord {
  binding_id: string;
  operation_id: string;
  workspace_id: string;
  operation_status:
    EnterpriseEvaluationOperationStatus;
  evidence_kind:
    EnterpriseEvaluationEvidenceKind;
  run: EvaluationRunRecord;
  gate_result: EvaluationGateResult | null;
  recorded_at: string;
  observed_at: string;
}

export interface WorkspaceEvaluationEvidenceList {
  workspace_id: string;
  records: WorkspaceEvaluationEvidenceRecord[];
}

export class WorkspaceEvaluationEvidenceError
extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "WorkspaceEvaluationEvidenceError";
    this.status = status;
    this.detail = detail;
  }
}

interface FetchWorkspaceEvaluationEvidenceListRequest {
  workspaceId: string;
  userId: string;
  limit?: number;
  signal?: AbortSignal;
}

interface FetchWorkspaceEvaluationEvidenceDetailRequest {
  workspaceId: string;
  userId: string;
  bindingId: string;
  signal?: AbortSignal;
}

const FORBIDDEN_EVIDENCE_ID_FIELD =
  "evidence_id";

function isRecord(
  value: unknown
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null
  );
}

function isNonEmptyString(
  value: unknown
): value is string {
  return (
    typeof value === "string" &&
    value.length > 0
  );
}

function isNullableNonEmptyString(
  value: unknown
): value is string | null {
  return (
    value === null ||
    isNonEmptyString(value)
  );
}

function isNonNegativeInteger(
  value: unknown
): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 0
  );
}

function isFiniteNumber(
  value: unknown
): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value)
  );
}

function isTimestamp(
  value: unknown
): value is string {
  return (
    isNonEmptyString(value) &&
    Number.isFinite(
      Date.parse(value)
    )
  );
}

function hasOwn(
  value: Record<string, unknown>,
  key: string
): boolean {
  return Object.prototype.hasOwnProperty.call(
    value,
    key
  );
}

function containsForbiddenEvidenceId(
  value: unknown
): boolean {
  if (Array.isArray(value)) {
    return value.some(
      containsForbiddenEvidenceId
    );
  }

  if (!isRecord(value)) {
    return false;
  }

  if (
    hasOwn(
      value,
      FORBIDDEN_EVIDENCE_ID_FIELD
    )
  ) {
    return true;
  }

  return Object.values(value).some(
    containsForbiddenEvidenceId
  );
}

function isEvalOpsVersion(
  value: unknown
): value is EvalOpsVersion {
  return value === "eval-ops-v1";
}

function isEvaluationMetric(
  value: unknown
): value is EvaluationMetric {
  return (
    value === "claim_preservation" ||
    value === "naturalness" ||
    value === "rewrite_distance" ||
    value === "latency_ms" ||
    value === "provider_error_rate"
  );
}

function isEvaluationComparator(
  value: unknown
): value is EvaluationComparator {
  return (
    value === "at_least" ||
    value === "at_most"
  );
}

function isEvaluationRunOutcome(
  value: unknown
): value is EvaluationRunOutcome {
  return (
    value === "succeeded" ||
    value === "failed"
  );
}

function isEvaluationGateDecision(
  value: unknown
): value is EvaluationGateDecision {
  return (
    value === "passed" ||
    value === "failed"
  );
}

function isOperationStatus(
  value: unknown
): value is EnterpriseEvaluationOperationStatus {
  return (
    value === "open" ||
    value === "succeeded" ||
    value === "failed"
  );
}

function isEvidenceKind(
  value: unknown
): value is EnterpriseEvaluationEvidenceKind {
  return (
    value === "run" ||
    value === "gate"
  );
}

function invalidResponse():
WorkspaceEvaluationEvidenceError {
  return new WorkspaceEvaluationEvidenceError(
    502,
    "invalid_workspace_evaluation_evidence_response"
  );
}

function requireDatasetIdentity(
  value: unknown
): EvaluationDatasetIdentity {
  if (
    !isRecord(value) ||
    !isEvalOpsVersion(
      value.eval_version
    ) ||
    !isNonEmptyString(
      value.dataset_id
    ) ||
    !isNonEmptyString(
      value.dataset_version
    )
  ) {
    throw invalidResponse();
  }

  return {
    eval_version: value.eval_version,
    dataset_id: value.dataset_id,
    dataset_version: value.dataset_version
  };
}

function requireRunIdentity(
  value: unknown
): EvaluationRunIdentity {
  if (
    !isRecord(value) ||
    !isEvalOpsVersion(
      value.eval_version
    ) ||
    !isNonEmptyString(
      value.run_id
    ) ||
    !isNonEmptyString(
      value.target_id
    )
  ) {
    throw invalidResponse();
  }

  return {
    eval_version: value.eval_version,
    run_id: value.run_id,
    dataset: requireDatasetIdentity(
      value.dataset
    ),
    target_id: value.target_id
  };
}

function requireMetricResult(
  value: unknown
): EvaluationMetricResult {
  if (
    !isRecord(value) ||
    !isEvaluationMetric(
      value.metric
    ) ||
    !isFiniteNumber(
      value.value
    )
  ) {
    throw invalidResponse();
  }

  return {
    metric: value.metric,
    value: value.value
  };
}

function requireRun(
  value: unknown
): EvaluationRunRecord {
  if (
    !isRecord(value) ||
    !isEvalOpsVersion(
      value.eval_version
    ) ||
    !isEvaluationRunOutcome(
      value.outcome
    ) ||
    !isNonNegativeInteger(
      value.evaluated_case_count
    ) ||
    !isNonNegativeInteger(
      value.failed_case_count
    ) ||
    !Array.isArray(
      value.metric_results
    ) ||
    !isNullableNonEmptyString(
      value.failure_reason
    )
  ) {
    throw invalidResponse();
  }

  if (
    value.failed_case_count >
    value.evaluated_case_count
  ) {
    throw invalidResponse();
  }

  const metricResults =
    value.metric_results.map(
      requireMetricResult
    );

  const metrics =
    metricResults.map(
      (result) => result.metric
    );

  if (
    new Set(metrics).size !==
    metrics.length
  ) {
    throw invalidResponse();
  }

  if (
    value.outcome === "succeeded"
  ) {
    if (
      value.evaluated_case_count < 1 ||
      metricResults.length < 1 ||
      value.failure_reason !== null
    ) {
      throw invalidResponse();
    }
  } else if (
    value.failure_reason === null
  ) {
    throw invalidResponse();
  }

  return {
    eval_version: value.eval_version,
    identity: requireRunIdentity(
      value.identity
    ),
    outcome: value.outcome,
    evaluated_case_count:
      value.evaluated_case_count,
    failed_case_count:
      value.failed_case_count,
    metric_results: metricResults,
    failure_reason:
      value.failure_reason
  };
}

function requireThreshold(
  value: unknown
): EvaluationThreshold {
  if (
    !isRecord(value) ||
    !isEvaluationMetric(
      value.metric
    ) ||
    !isEvaluationComparator(
      value.comparator
    ) ||
    !isFiniteNumber(
      value.threshold
    )
  ) {
    throw invalidResponse();
  }

  return {
    metric: value.metric,
    comparator: value.comparator,
    threshold: value.threshold
  };
}

function requireQualityGate(
  value: unknown
): EvaluationQualityGate {
  if (
    !isRecord(value) ||
    !isEvalOpsVersion(
      value.eval_version
    ) ||
    !isNonEmptyString(
      value.gate_id
    ) ||
    !Array.isArray(
      value.thresholds
    ) ||
    value.thresholds.length < 1
  ) {
    throw invalidResponse();
  }

  const thresholds =
    value.thresholds.map(
      requireThreshold
    );

  const metrics =
    thresholds.map(
      (threshold) =>
        threshold.metric
    );

  if (
    new Set(metrics).size !==
    metrics.length
  ) {
    throw invalidResponse();
  }

  return {
    eval_version: value.eval_version,
    gate_id: value.gate_id,
    thresholds
  };
}

function thresholdPasses(
  threshold: EvaluationThreshold,
  value: number
): boolean {
  if (
    threshold.comparator ===
    "at_least"
  ) {
    return (
      value >= threshold.threshold
    );
  }

  return (
    value <= threshold.threshold
  );
}

function requireGateResult(
  value: unknown
): EvaluationGateResult {
  if (
    !isRecord(value) ||
    !isEvalOpsVersion(
      value.eval_version
    ) ||
    !isNonEmptyString(
      value.run_id
    ) ||
    !isEvaluationGateDecision(
      value.decision
    ) ||
    !Array.isArray(
      value.metric_results
    ) ||
    value.metric_results.length < 1
  ) {
    throw invalidResponse();
  }

  const gate =
    requireQualityGate(
      value.gate
    );

  const metricResults =
    value.metric_results.map(
      requireMetricResult
    );

  const resultByMetric =
    new Map<
      EvaluationMetric,
      EvaluationMetricResult
    >();

  for (
    const result of metricResults
  ) {
    if (
      resultByMetric.has(
        result.metric
      )
    ) {
      throw invalidResponse();
    }

    resultByMetric.set(
      result.metric,
      result
    );
  }

  if (
    resultByMetric.size !==
    gate.thresholds.length
  ) {
    throw invalidResponse();
  }

  for (
    const threshold of gate.thresholds
  ) {
    if (
      !resultByMetric.has(
        threshold.metric
      )
    ) {
      throw invalidResponse();
    }
  }

  const passed =
    gate.thresholds.every(
      (threshold) => {
        const result =
          resultByMetric.get(
            threshold.metric
          );

        return (
          result !== undefined &&
          thresholdPasses(
            threshold,
            result.value
          )
        );
      }
    );

  const expectedDecision:
  EvaluationGateDecision =
    passed
      ? "passed"
      : "failed";

  if (
    value.decision !==
    expectedDecision
  ) {
    throw invalidResponse();
  }

  return {
    eval_version: value.eval_version,
    gate,
    run_id: value.run_id,
    decision: value.decision,
    metric_results: metricResults
  };
}

function requireEvidenceRecord(
  value: unknown,
  {
    expectedWorkspaceId,
    expectedBindingId
  }: {
    expectedWorkspaceId: string;
    expectedBindingId?: string;
  }
): WorkspaceEvaluationEvidenceRecord {
  if (
    !isRecord(value) ||
    !isNonEmptyString(
      value.binding_id
    ) ||
    !isNonEmptyString(
      value.operation_id
    ) ||
    !isNonEmptyString(
      value.workspace_id
    ) ||
    value.workspace_id !==
      expectedWorkspaceId ||
    !isOperationStatus(
      value.operation_status
    ) ||
    !isEvidenceKind(
      value.evidence_kind
    ) ||
    !isTimestamp(
      value.recorded_at
    ) ||
    !isTimestamp(
      value.observed_at
    )
  ) {
    throw invalidResponse();
  }

  if (
    expectedBindingId !== undefined &&
    value.binding_id !==
      expectedBindingId
  ) {
    throw invalidResponse();
  }

  const run =
    requireRun(
      value.run
    );

  let gateResult:
    EvaluationGateResult | null;

  if (
    value.evidence_kind === "run"
  ) {
    if (
      value.gate_result !== null
    ) {
      throw invalidResponse();
    }

    gateResult = null;
  } else {
    if (
      value.gate_result === null
    ) {
      throw invalidResponse();
    }

    gateResult =
      requireGateResult(
        value.gate_result
      );

    if (
      gateResult.run_id !==
      run.identity.run_id
    ) {
      throw invalidResponse();
    }
  }

  /*
   * Operation lifecycle and evaluation outcome
   * are deliberately independent. In particular:
   *
   * operation_status === "succeeded"
   * run.outcome === "failed"
   *
   * is a valid representation.
   */

  return {
    binding_id: value.binding_id,
    operation_id: value.operation_id,
    workspace_id: value.workspace_id,
    operation_status:
      value.operation_status,
    evidence_kind:
      value.evidence_kind,
    run,
    gate_result: gateResult,
    recorded_at: value.recorded_at,
    observed_at: value.observed_at
  };
}

function requireList(
  payload: unknown,
  {
    expectedWorkspaceId
  }: {
    expectedWorkspaceId: string;
  }
): WorkspaceEvaluationEvidenceList {
  if (
    containsForbiddenEvidenceId(
      payload
    ) ||
    !isRecord(payload) ||
    !isNonEmptyString(
      payload.workspace_id
    ) ||
    payload.workspace_id !==
      expectedWorkspaceId ||
    !Array.isArray(
      payload.records
    )
  ) {
    throw invalidResponse();
  }

  const records =
    payload.records.map(
      (record) =>
        requireEvidenceRecord(
          record,
          {
            expectedWorkspaceId
          }
        )
    );

  const bindingIds =
    records.map(
      (record) =>
        record.binding_id
    );

  if (
    new Set(bindingIds).size !==
    bindingIds.length
  ) {
    throw invalidResponse();
  }

  return {
    workspace_id:
      payload.workspace_id,
    records
  };
}

function requireDetail(
  payload: unknown,
  {
    expectedWorkspaceId,
    expectedBindingId
  }: {
    expectedWorkspaceId: string;
    expectedBindingId: string;
  }
): WorkspaceEvaluationEvidenceRecord {
  if (
    containsForbiddenEvidenceId(
      payload
    )
  ) {
    throw invalidResponse();
  }

  return requireEvidenceRecord(
    payload,
    {
      expectedWorkspaceId,
      expectedBindingId
    }
  );
}

async function readUnknownJson(
  response: Response
): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw invalidResponse();
  }
}

async function throwHttpError(
  response: Response
): Promise<never> {
  let detail =
    `workspace_evaluation_evidence_http_${response.status}`;

  try {
    const payload: unknown =
      await response.json();

    if (
      isRecord(payload) &&
      typeof payload.detail ===
        "string"
    ) {
      detail = payload.detail;
    }
  } catch {
    // Preserve status-derived detail.
  }

  throw new WorkspaceEvaluationEvidenceError(
    response.status,
    detail
  );
}

export async function fetchWorkspaceEvaluationEvidenceList({
  workspaceId,
  userId,
  limit = 50,
  signal
}: FetchWorkspaceEvaluationEvidenceListRequest):
Promise<WorkspaceEvaluationEvidenceList> {
  const query =
    new URLSearchParams({
      user_id: userId,
      limit: String(limit)
    });

  const response =
    await fetch(
      `/api/v2/workspaces/${encodeURIComponent(
        workspaceId
      )}/evaluation-evidence?${query.toString()}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json"
        },
        signal
      }
    );

  if (!response.ok) {
    await throwHttpError(
      response
    );
  }

  const payload =
    await readUnknownJson(
      response
    );

  return requireList(
    payload,
    {
      expectedWorkspaceId:
        workspaceId
    }
  );
}

export async function fetchWorkspaceEvaluationEvidenceDetail({
  workspaceId,
  userId,
  bindingId,
  signal
}: FetchWorkspaceEvaluationEvidenceDetailRequest):
Promise<WorkspaceEvaluationEvidenceRecord> {
  const query =
    new URLSearchParams({
      user_id: userId
    });

  const response =
    await fetch(
      `/api/v2/workspaces/${encodeURIComponent(
        workspaceId
      )}/evaluation-evidence/${encodeURIComponent(
        bindingId
      )}?${query.toString()}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json"
        },
        signal
      }
    );

  if (!response.ok) {
    await throwHttpError(
      response
    );
  }

  const payload =
    await readUnknownJson(
      response
    );

  return requireDetail(
    payload,
    {
      expectedWorkspaceId:
        workspaceId,
      expectedBindingId:
        bindingId
    }
  );
}
