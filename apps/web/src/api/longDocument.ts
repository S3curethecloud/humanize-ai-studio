export interface LongDocumentSection {
  section_id: string;
  ordinal: number;
  start_offset: number;
  end_offset: number;
  source_text: string;
  heading: string | null;
  eligible_for_rewrite: boolean;
}

export interface LongDocumentStructure {
  structure_id: string;
  source_text: string;
  sections: LongDocumentSection[];
}

export interface LongDocumentSectionResult {
  section_id: string;
  ordinal: number;
  disposition: "rewrite" | "preserve";
  source_text: string;
  rewritten_text: string;
}

export interface DocumentReconstruction {
  structure: LongDocumentStructure;
  section_results: LongDocumentSectionResult[];
  reconstructed_text: string;
}

export interface LongDocumentAuditRecord {
  audit_id: string;
  workspace_id: string;
  user_id: string;
  created_at?: string;
}

export interface LongDocumentRewriteResponse {
  reconstruction: DocumentReconstruction;
  audit: LongDocumentAuditRecord;
  claim_lock?: unknown;
}

export interface LongDocumentRewriteRequest {
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

export async function submitLongDocumentRewrite(
  workspaceId: string,
  userId: string,
  rewrite: LongDocumentRewriteRequest
): Promise<LongDocumentRewriteResponse> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/long-document-rewrites`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        user_id: userId,
        rewrite
      })
    }
  );

  if (!response.ok) {
    let detail =
      `Long-document rewrite failed with status ${response.status}.`;

    try {
      const body = (await response.json()) as {
        detail?: unknown;
      };

      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Preserve the status-based error.
    }

    throw new Error(detail);
  }

  return (await response.json()) as
    LongDocumentRewriteResponse;
}
