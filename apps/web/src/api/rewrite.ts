export type RewriteDecision =
  | "no_change"
  | "minimal_edit"
  | "full_rewrite";

export type RewriteSignalType =
  | "formulaic_language"
  | "repetition"
  | "verbosity"
  | "intensity_request"
  | "already_clear";

export type ReleaseDecision = "pass" | "warn" | "fail";

export type EditorialQualityDecision = "pass" | "review";

export interface RewriteNecessitySignal {
  signal_type: RewriteSignalType;
  description: string;
  score: number;
  evidence: string[];
}

export interface RewriteNecessityEvidence {
  decision: RewriteDecision;
  score: number;
  provider_required: boolean;
  signals: RewriteNecessitySignal[];
  rationale: string;
}

export interface ProviderUsageEvidence {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
}

export interface ProviderExecutionEvidence {
  latency_ms: number;
  primary_provider_name: string;
  actual_provider_name: string;
  fallback_used: boolean;
  provider_error_category: string | null;
  usage: ProviderUsageEvidence;
}

export interface VerificationResult {
  decision: ReleaseDecision;
  preserved_facts: string[];
  missing_facts: string[];
  unexpected_facts: string[];
  warnings: string[];
}

export interface EditorialQualityResult {
  decision: EditorialQualityDecision;
  naturalness_score: number;
  source_flag_count: number;
  remaining_flag_count: number;
  removed_flag_count: number;
  warnings: string[];
}

export interface RewriteResponse {
  trace_id: string;
  source_text: string;
  rewritten_text: string;
  provider_name: string;
  model_name: string;
  prompt_version: string;
  provider_execution: ProviderExecutionEvidence;
  rewrite_necessity: RewriteNecessityEvidence;
  verification: VerificationResult;
  editorial_quality: EditorialQualityResult;
}

export interface RewriteRequest {
  text: string;
  document_type:
    | "general"
    | "professional_email"
    | "interview_answer"
    | "technical_document"
    | "social_post";
  audience: string;
  tone: string;
  intensity:
    | "light_edit"
    | "natural_rewrite"
    | "deep_reconstruction";
  preserve_numbers: boolean;
  preserve_dates: boolean;
}

export async function submitRewrite(
  request: RewriteRequest
): Promise<RewriteResponse> {
  const response = await fetch("/api/v1/rewrites", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let detail = `Rewrite failed with status ${response.status}.`;

    try {
      const body = (await response.json()) as {
        detail?: unknown;
      };

      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Preserve the status-based error when the body is not JSON.
    }

    throw new Error(detail);
  }

  return (await response.json()) as RewriteResponse;
}
