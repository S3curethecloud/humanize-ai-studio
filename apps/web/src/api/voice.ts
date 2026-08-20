export type VoiceProfileStatus =
  | "active"
  | "archived";

export type VoiceAnalysisState =
  | "never_analyzed"
  | "current"
  | "stale";

export interface VoiceStyleAttributes {
  formality: "casual" | "balanced" | "formal";
  sentence_length: "short" | "mixed" | "long";
  directness: "direct" | "balanced" | "indirect";
  warmth: "reserved" | "balanced" | "warm";
  concision: "concise" | "balanced" | "expansive";
  first_person_frequency: "low" | "moderate" | "high";
  contraction_preference: "avoid" | "mixed" | "prefer";
  transition_style: "minimal" | "natural" | "explicit";
}

export interface VoiceSourceSample {
  sample_id: string;
  text: string;
  label: string | null;
  created_at: string;
}

export interface VoiceAnalysisProvenance {
  analyzer_version: string;
  analyzed_at: string;
  source_sample_ids: string[];
  source_fingerprint: string;
  sample_count: number;
  sufficiency:
    | "insufficient"
    | "limited"
    | "strong";
  consistency:
    | "not_applicable"
    | "coherent"
    | "mixed"
    | "divergent";
}

export interface VoiceProfile {
  profile_id: string;
  workspace_id: string;
  created_by_user_id: string;
  name: string;
  description: string | null;
  status: VoiceProfileStatus;
  source_samples: VoiceSourceSample[];
  style_attributes: VoiceStyleAttributes;
  analysis_state: VoiceAnalysisState;
  analysis_provenance: VoiceAnalysisProvenance | null;
  created_at: string;
  updated_at: string;
}

export interface VoiceAnalysisSignal {
  attribute: string;
  inferred_value: string;
  metric_name: string;
  metric_value: number;
  rationale: string;
}

export interface VoiceAnalysisEvidence {
  analyzer_version: string;
  sufficiency:
    | "insufficient"
    | "limited"
    | "strong";
  sample_consistency: {
    classification:
      | "not_applicable"
      | "coherent"
      | "mixed"
      | "divergent";
    agreement_ratio: number | null;
    consistent_attribute_count: number;
    total_attribute_count: number;
    divergent_attributes: string[];
  };
  sample_count: number;
  character_count: number;
  word_count: number;
  sentence_count: number;
  signals: VoiceAnalysisSignal[];
}

async function parseError(
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

export async function listVoiceProfiles(
  workspaceId: string,
  userId: string
): Promise<VoiceProfile[]> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/voice-profiles?user_id=${encodeURIComponent(
      userId
    )}`
  );

  if (!response.ok) {
    throw await parseError(
      response,
      `Voice profile list failed with status ${response.status}.`
    );
  }

  const payload = (await response.json()) as {
    profiles: VoiceProfile[];
  };

  return payload.profiles;
}

export async function createVoiceProfile(
  workspaceId: string,
  userId: string,
  input: {
    name: string;
    description?: string;
    sampleText: string;
  }
): Promise<VoiceProfile> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/voice-profiles`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        user_id: userId,
        name: input.name,
        description:
          input.description?.trim() || null,
        source_samples: [
          {
            sample_id: crypto.randomUUID(),
            text: input.sampleText,
            label: "Primary writing sample"
          }
        ]
      })
    }
  );

  if (!response.ok) {
    throw await parseError(
      response,
      `Voice profile creation failed with status ${response.status}.`
    );
  }

  const payload = (await response.json()) as {
    profile: VoiceProfile;
  };

  return payload.profile;
}

export async function analyzeVoiceProfile(
  workspaceId: string,
  userId: string,
  profileId: string
): Promise<{
  profile: VoiceProfile;
  evidence: VoiceAnalysisEvidence;
}> {
  const response = await fetch(
    `/api/v2/workspaces/${encodeURIComponent(
      workspaceId
    )}/voice-profiles/${encodeURIComponent(
      profileId
    )}/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        user_id: userId
      })
    }
  );

  if (!response.ok) {
    throw await parseError(
      response,
      `Voice analysis failed with status ${response.status}.`
    );
  }

  return (await response.json()) as {
    profile: VoiceProfile;
    evidence: VoiceAnalysisEvidence;
  };
}
