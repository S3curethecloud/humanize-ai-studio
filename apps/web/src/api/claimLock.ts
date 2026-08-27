export type ClaimLockEnforcementMode =
  | "strict"
  | "audit_only";

export type ClaimLockOrigin =
  | "request"
  | "workspace"
  | "system";

export type ProtectedValueKind =
  | "number"
  | "date"
  | "percentage"
  | "identifier"
  | "url"
  | "code"
  | "other";

export interface ClaimLockProvenance {
  origin: ClaimLockOrigin;
  source_reference?: string | null;
}

export interface ProtectedClaim {
  claim_id: string;
  text: string;
  provenance: ClaimLockProvenance;
}

export interface ProtectedTerm {
  term_id: string;
  text: string;
  case_sensitive: boolean;
  provenance: ClaimLockProvenance;
}

export interface ProtectedValue {
  value_id: string;
  value: string;
  kind: ProtectedValueKind;
  provenance: ClaimLockProvenance;
}

export interface ClaimLock {
  lock_id: string;
  enforcement_mode: ClaimLockEnforcementMode;
  claims: ProtectedClaim[];
  terms: ProtectedTerm[];
  values: ProtectedValue[];
  created_at: string;
}

export type ClaimExtractionDecision =
  | "selected"
  | "skipped";

export type ClaimExtractionReason =
  | "selected"
  | "below_minimum_words"
  | "question_excluded";

export interface ClaimSelectionPolicy {
  minimum_word_count: number;
  include_questions: boolean;
}

export interface ClaimExtractionSegmentEvidence {
  start: number;
  end: number;
  matched_text: string;
  word_count: number;
  decision: ClaimExtractionDecision;
  reason: ClaimExtractionReason;
  claim_id?: string | null;
}

export interface ClaimExtractionResult {
  extractor_version: "claim-extractor-v1";
  policy: ClaimSelectionPolicy;
  claims: ProtectedClaim[];
  segments: ClaimExtractionSegmentEvidence[];
}

export type ClaimLockExtractionDetector =
  | "explicit_term"
  | "url"
  | "percentage"
  | "date"
  | "code"
  | "identifier"
  | "number";

export interface ClaimLockExtractionOccurrence {
  item_id: string;
  item_type: "term" | "value";
  detector: ClaimLockExtractionDetector;
  start: number;
  end: number;
  matched_text: string;
}

export interface ClaimLockExtractionResult {
  extractor_version: "claim-lock-extractor-v1";
  terms: ProtectedTerm[];
  values: ProtectedValue[];
  occurrences: ClaimLockExtractionOccurrence[];
}

export interface ClaimLockPreparationResult {
  preparation_version: "claim-lock-preparation-v1";
  claim_extraction: ClaimExtractionResult;
  protected_item_extraction: ClaimLockExtractionResult;
  claim_lock?: ClaimLock | null;
}

export type ClaimLockValidationDecision =
  | "pass"
  | "violation";

export type ClaimLockCheckStatus =
  | "preserved"
  | "missing"
  | "not_evaluated";

export interface ClaimLockValidationCheck {
  item_id: string;
  item_type: "claim" | "term" | "value";
  expected_text: string;
  status: ClaimLockCheckStatus;
  reason: string;
}

export interface ClaimLockValidationResult {
  validator_version: "claim-lock-validator-v1";
  lock_id?: string | null;
  enforcement_mode?: ClaimLockEnforcementMode | null;
  decision: ClaimLockValidationDecision;
  checks: ClaimLockValidationCheck[];
}

export interface ClaimLockValidationAuditSnapshot {
  validator_version: "claim-lock-validator-v1";
  lock_id: string;
  enforcement_mode: ClaimLockEnforcementMode;
  decision: ClaimLockValidationDecision;
  checks: ClaimLockValidationCheck[];
}

export interface EnterpriseClaimLockWorkspacePolicyExecutionEvidence {
  evidence_version:
    "enterprise-claim-lock-workspace-policy-execution-v1";
  policy_version:
    "enterprise-workspace-claim-lock-policy-v1";
  policy_id: string;
  policy_revision: number;
  enforcement_mode: ClaimLockEnforcementMode;
  applicable_term_ids: string[];
}

export interface ClaimLockRewriteEvidence {
  preparation: ClaimLockPreparationResult;
  validation: ClaimLockValidationResult;
  workspace_policy?:
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence
    | null;
}

export interface ClaimLockRequestProtectedTerm {
  text: string;
  case_sensitive: boolean;
}

export interface ClaimLockRequestCustomization {
  protected_terms?: ClaimLockRequestProtectedTerm[];
  claim_lock_enforcement_mode?:
    ClaimLockEnforcementMode;
}

export type EnterpriseClaimLockPolicyStatus =
  | "active"
  | "disabled"
  | "archived";

export interface EnterpriseWorkspaceClaimLockPolicy {
  policy_version:
    "enterprise-workspace-claim-lock-policy-v1";
  policy_id: string;
  workspace_id: string;
  status: EnterpriseClaimLockPolicyStatus;
  enforcement_mode: ClaimLockEnforcementMode;
  protected_terms: ProtectedTerm[];
  created_by_user_id: string;
  created_at: string;
  updated_by_user_id: string;
  updated_at: string;
  revision: number;
}

export interface EnterpriseClaimLockPolicyTermInput {
  term_id: string;
  text: string;
  case_sensitive: boolean;
}

export interface CreateEnterpriseClaimLockPolicyInput {
  actor_user_id: string;
  policy_id: string;
  enforcement_mode: ClaimLockEnforcementMode;
  protected_terms:
    EnterpriseClaimLockPolicyTermInput[];
}

export interface UpdateEnterpriseClaimLockPolicyInput {
  actor_user_id: string;
  policy_id: string;
  expected_revision: number;
  enforcement_mode: ClaimLockEnforcementMode;
  protected_terms:
    EnterpriseClaimLockPolicyTermInput[];
}

export interface EnterpriseClaimLockPolicyLifecycleInput {
  actor_user_id: string;
  policy_id: string;
  expected_revision: number;
}

interface EnterpriseClaimLockPolicyResponse {
  policy: EnterpriseWorkspaceClaimLockPolicy;
}

export class EnterpriseClaimLockApiError
extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(
    status: number,
    detail: string
  ) {
    super(detail);
    this.name = "EnterpriseClaimLockApiError";
    this.status = status;
    this.detail = detail;
  }
}

function isRecord(
  value: unknown
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null
  );
}

async function requestClaimLockPolicy(
  url: string,
  init?: RequestInit
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  const response = await fetch(
    url,
    {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body !== undefined
          ? {
              "Content-Type":
                "application/json"
            }
          : {})
      }
    }
  );

  if (!response.ok) {
    let detail =
      `claim_lock_policy_http_${response.status}`;

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

    throw new EnterpriseClaimLockApiError(
      response.status,
      detail
    );
  }

  const payload =
    (await response.json()) as
      EnterpriseClaimLockPolicyResponse;

  return payload.policy;
}

export async function getEnterpriseClaimLockPolicy(
  workspaceId: string,
  actorUserId: string
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  const query = new URLSearchParams({
    actor_user_id: actorUserId
  });

  return requestClaimLockPolicy(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/claim-lock-policy?${query.toString()}`
  );
}

export async function createEnterpriseClaimLockPolicy(
  workspaceId: string,
  input: CreateEnterpriseClaimLockPolicyInput
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  return requestClaimLockPolicy(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/claim-lock-policy`,
    {
      method: "POST",
      body: JSON.stringify(input)
    }
  );
}

export async function updateEnterpriseClaimLockPolicy(
  workspaceId: string,
  input: UpdateEnterpriseClaimLockPolicyInput
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  return requestClaimLockPolicy(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/claim-lock-policy`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    }
  );
}

async function changeEnterpriseClaimLockPolicyStatus(
  workspaceId: string,
  action: "enable" | "disable" | "archive",
  input: EnterpriseClaimLockPolicyLifecycleInput
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  return requestClaimLockPolicy(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/claim-lock-policy/${action}`,
    {
      method: "POST",
      body: JSON.stringify(input)
    }
  );
}

export async function enableEnterpriseClaimLockPolicy(
  workspaceId: string,
  input: EnterpriseClaimLockPolicyLifecycleInput
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  return changeEnterpriseClaimLockPolicyStatus(
    workspaceId,
    "enable",
    input
  );
}

export async function disableEnterpriseClaimLockPolicy(
  workspaceId: string,
  input: EnterpriseClaimLockPolicyLifecycleInput
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  return changeEnterpriseClaimLockPolicyStatus(
    workspaceId,
    "disable",
    input
  );
}

export async function archiveEnterpriseClaimLockPolicy(
  workspaceId: string,
  input: EnterpriseClaimLockPolicyLifecycleInput
): Promise<EnterpriseWorkspaceClaimLockPolicy> {
  return changeEnterpriseClaimLockPolicyStatus(
    workspaceId,
    "archive",
    input
  );
}
