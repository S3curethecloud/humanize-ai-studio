import type {
  ClaimLock,
  ClaimLockEnforcementMode,
  ClaimLockValidationAuditSnapshot,
  EnterpriseClaimLockWorkspacePolicyExecutionEvidence
} from "./claimLock";

export interface RewriteHistoryRecord {
  rewrite_id: string;
  workspace_id: string;
  user_id: string;
  trace_id: string;
  source_text: string;
  rewritten_text: string;
  document_type: string;
  audience: string;
  tone: string;
  intensity: string;
  provider_name: string;
  model_name: string;
  prompt_version: string;
  voice_profile_id?: string | null;
  voice_guidance_version?: string | null;
  claim_lock_snapshot?: ClaimLock | null;
  claim_lock_validation?:
    ClaimLockValidationAuditSnapshot | null;
  claim_lock_enforcement_mode?:
    ClaimLockEnforcementMode | null;
  claim_lock_workspace_policy?:
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence
    | null;
  fallback_used: boolean;
  verification_decision: string;
  editorial_quality_decision: string;
  status: string;
  created_at: string;
}

export async function listWorkspaceHistory(
  workspaceId: string,
  userId: string,
  limit = 50
): Promise<RewriteHistoryRecord[]> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/history?user_id=${encodeURIComponent(
      userId
    )}&limit=${limit}`
  );

  if (!response.ok) {
    let detail =
      `History request failed with status ${response.status}.`;

    try {
      const body = (await response.json()) as {
        detail?: unknown;
      };

      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Preserve status-based error.
    }

    throw new Error(detail);
  }

  const payload = (await response.json()) as {
    records: RewriteHistoryRecord[];
  };

  return payload.records;
}
