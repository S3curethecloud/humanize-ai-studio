import type {
  RewriteDecision,
  RewriteNecessityEvidence,
  RewriteSignalType
} from "../api/rewrite";

export type DecisionTone =
  | "success"
  | "information"
  | "emphasis";

export interface RewriteDecisionPresentation {
  label: string;
  headline: string;
  explanation: string;
  badge: string;
  tone: DecisionTone;
}

const DECISION_PRESENTATIONS: Record<
  RewriteDecision,
  RewriteDecisionPresentation
> = {
  no_change: {
    label: "No rewrite needed",
    headline: "Your original wording was preserved",
    explanation:
      "The text was already clear and did not require provider reconstruction.",
    badge: "Original preserved",
    tone: "success"
  },
  minimal_edit: {
    label: "Light cleanup applied",
    headline: "Only localized edits were needed",
    explanation:
      "A few formulaic or unnecessary phrases were cleaned up without invoking the configured rewrite provider.",
    badge: "Zero-token edit",
    tone: "information"
  },
  full_rewrite: {
    label: "Full rewrite applied",
    headline: "Broader structural improvement was needed",
    explanation:
      "The text required more substantial reconstruction, so the configured rewrite provider was used.",
    badge: "Provider used",
    tone: "emphasis"
  }
};

const SIGNAL_LABELS: Record<RewriteSignalType, string> = {
  already_clear: "Already clear",
  formulaic_language: "Formulaic language",
  repetition: "Structural repetition",
  verbosity: "Sentence complexity",
  intensity_request: "Requested rewrite depth"
};

export function presentRewriteDecision(
  evidence: RewriteNecessityEvidence
): RewriteDecisionPresentation {
  return DECISION_PRESENTATIONS[evidence.decision];
}

export function presentSignalLabel(
  signalType: RewriteSignalType
): string {
  return SIGNAL_LABELS[signalType];
}

export function formatTokenCount(
  value: number | null
): string {
  return value === null
    ? "Not reported"
    : value.toLocaleString();
}

export function formatLatency(
  latencyMs: number
): string {
  if (latencyMs < 1) {
    return "< 1 ms";
  }

  if (latencyMs < 1000) {
    return `${Math.round(latencyMs)} ms`;
  }

  return `${(latencyMs / 1000).toFixed(2)} s`;
}
