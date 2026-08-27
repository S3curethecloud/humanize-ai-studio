import {
  FormEvent,
  useEffect,
  useMemo,
  useState
} from "react";

import type {
  ClaimLockEnforcementMode,
  ClaimLockRequestCustomization
} from "../api/claimLock";
import {
  submitWorkspaceRewrite,
  type RewriteRequest,
  type WorkspaceRewriteResponse
} from "../api/rewrite";
import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";
import ClaimLockExecutionEvidence from "../components/ClaimLockExecutionEvidence";
import { RewriteAuditDetails } from "../components/RewriteAuditDetails";
import { RewriteDecisionCard } from "../components/RewriteDecisionCard";

const DEFAULT_TEXT =
  "Furthermore, it is important to note that the team completed the migration in 30 days.";

const INITIAL_REQUEST: RewriteRequest = {
  text: DEFAULT_TEXT,
  document_type: "general",
  audience: "general audience",
  tone: "natural and clear",
  intensity: "natural_rewrite",
  preserve_numbers: true,
  preserve_dates: true
};

type RequestClaimLockMode =
  | ""
  | ClaimLockEnforcementMode;

interface RequestClaimLockTermDraft {
  text: string;
  case_sensitive: boolean;
}

interface SubmittedResult {
  request: RewriteRequest;
  claimLock?: ClaimLockRequestCustomization;
  response: WorkspaceRewriteResponse;
}

function buildClaimLockCustomization(
  terms: RequestClaimLockTermDraft[],
  mode: RequestClaimLockMode
): ClaimLockRequestCustomization | undefined {
  const protectedTerms = terms
    .map((term) => ({
      text: term.text.trim(),
      case_sensitive: term.case_sensitive
    }))
    .filter(
      (term) => term.text !== ""
    );

  if (
    protectedTerms.length === 0 &&
    mode === ""
  ) {
    return undefined;
  }

  return {
    ...(protectedTerms.length > 0
      ? {
          protected_terms: protectedTerms
        }
      : {}),
    ...(mode !== ""
      ? {
          claim_lock_enforcement_mode: mode
        }
      : {})
  };
}

function cloneClaimLockCustomization(
  customization:
    ClaimLockRequestCustomization | undefined
): ClaimLockRequestCustomization | undefined {
  if (customization === undefined) {
    return undefined;
  }

  return {
    ...(customization.protected_terms !== undefined
      ? {
          protected_terms:
            customization.protected_terms.map(
              (term) => ({
                ...term
              })
            )
        }
      : {}),
    ...(customization
      .claim_lock_enforcement_mode !== undefined
      ? {
          claim_lock_enforcement_mode:
            customization
              .claim_lock_enforcement_mode
        }
      : {})
  };
}

function customizationsMatch(
  current:
    ClaimLockRequestCustomization | undefined,
  submitted:
    ClaimLockRequestCustomization | undefined
): boolean {
  if (
    current === undefined ||
    submitted === undefined
  ) {
    return (
      current === undefined &&
      submitted === undefined
    );
  }

  if (
    current.claim_lock_enforcement_mode !==
    submitted.claim_lock_enforcement_mode
  ) {
    return false;
  }

  const currentTerms =
    current.protected_terms ?? [];
  const submittedTerms =
    submitted.protected_terms ?? [];

  if (
    currentTerms.length !==
    submittedTerms.length
  ) {
    return false;
  }

  return currentTerms.every(
    (term, index) =>
      term.text === submittedTerms[index]?.text &&
      term.case_sensitive ===
        submittedTerms[index]?.case_sensitive
  );
}

const INTENSITY_LABELS: Record<
  RewriteRequest["intensity"],
  string
> = {
  light_edit: "Light edit",
  natural_rewrite: "Natural rewrite",
  deep_reconstruction: "Deep reconstruction"
};

const DOCUMENT_TYPE_LABELS: Record<
  RewriteRequest["document_type"],
  string
> = {
  general: "General",
  professional_email: "Professional email",
  interview_answer: "Interview answer",
  technical_document: "Technical document",
  social_post: "Social post"
};

function cloneRequest(
  request: RewriteRequest
): RewriteRequest {
  return {
    ...request
  };
}

function requestsMatch(
  current: RewriteRequest,
  submitted: RewriteRequest
): boolean {
  return (
    current.text === submitted.text &&
    current.document_type === submitted.document_type &&
    current.audience === submitted.audience &&
    current.tone === submitted.tone &&
    current.intensity === submitted.intensity &&
    current.preserve_numbers === submitted.preserve_numbers &&
    current.preserve_dates === submitted.preserve_dates
  );
}

interface RewriteStudioPageProps {
  accessContext: EnterpriseAccessContextState;
}

export default function RewriteStudioPage({
  accessContext
}: RewriteStudioPageProps) {
  const [request, setRequest] =
    useState<RewriteRequest>(INITIAL_REQUEST);

  const [claimLockMode, setClaimLockMode] =
    useState<RequestClaimLockMode>("");

  const [claimLockTerms, setClaimLockTerms] =
    useState<RequestClaimLockTermDraft[]>([]);

  const [submittedResult, setSubmittedResult] =
    useState<SubmittedResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copyState, setCopyState] = useState<
    "idle" | "copied" | "failed"
  >("idle");

  const canCustomizeClaimLock =
    accessContext.context?.permissions.includes(
      "claim_lock.use"
    ) ?? false;

  const currentClaimLockCustomization =
    useMemo(
      () =>
        canCustomizeClaimLock
          ? buildClaimLockCustomization(
              claimLockTerms,
              claimLockMode
            )
          : undefined,
      [
        canCustomizeClaimLock,
        claimLockMode,
        claimLockTerms
      ]
    );

  const response =
    submittedResult?.response.rewrite ?? null;

  const isResultStale = useMemo(() => {
    if (submittedResult === null) {
      return false;
    }

    return (
      !requestsMatch(
        request,
        submittedResult.request
      ) ||
      !customizationsMatch(
        currentClaimLockCustomization,
        submittedResult.claimLock
      )
    );
  }, [
    currentClaimLockCustomization,
    request,
    submittedResult
  ]);

  useEffect(() => {
    setCopyState("idle");
  }, [response?.trace_id]);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError(null);
    setIsSubmitting(true);
    setCopyState("idle");

    const requestSnapshot = cloneRequest(request);
    const claimLockSnapshot =
      cloneClaimLockCustomization(
        currentClaimLockCustomization
      );

    if (
      accessContext.status !== "connected" ||
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      setError(
        "Canonical workspace access context is required before rewriting."
      );
      setIsSubmitting(false);
      return;
    }

    try {
      const result =
        await submitWorkspaceRewrite(
          accessContext.workspaceId,
          accessContext.userId,
          requestSnapshot,
          claimLockSnapshot
        );

      setSubmittedResult({
        request: requestSnapshot,
        claimLock: claimLockSnapshot,
        response: result
      });
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "The rewrite request failed."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCopyResult() {
    if (response === null) {
      return;
    }

    try {
      await navigator.clipboard.writeText(
        response.rewritten_text
      );
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (


      <main className="workspace workspace--enterprise">
        <header className="workspace-header workspace-header--enterprise">
          <div>
            <p className="eyebrow">
              Humanize Studio · Rewrite Studio
            </p>

            <h1>Enterprise Rewrite Workspace</h1>

            <p>
              Transform content with meaning preservation,
              governed execution, factual verification, and
              auditable provider evidence.
            </p>
          </div>

          <div className="system-badge">
            Governed workflow
          </div>
        </header>

        <section
          className="rewrite-control-strip"
          aria-label="Rewrite governance model"
        >
          <article>
            <span>01</span>
            <div>
              <strong>Meaning preservation</strong>
              <p>
                Facts, numbers, dates, and intent remain
                protected through verification.
              </p>
            </div>
          </article>

          <article>
            <span>02</span>
            <div>
              <strong>Governed routing</strong>
              <p>
                Provider selection remains a control-plane
                responsibility, not an editor control.
              </p>
            </div>
          </article>

          <article>
            <span>03</span>
            <div>
              <strong>Audit evidence</strong>
              <p>
                Rewrite decisions and provider execution
                remain visible after each submission.
              </p>
            </div>
          </article>
        </section>

        <section className="studio-grid studio-grid--enterprise" id="studio">
          <form
            className="editor-card editor-card--workspace"
            onSubmit={handleSubmit}
          >
            <div className="workspace-panel-label">
              <span>Source workspace</span>
              <strong>Draft and transformation controls</strong>
            </div>
            <div className="card-header">
              <div>
                <p className="eyebrow">Source text</p>
                <h2>Text to improve</h2>
              </div>

              <span>
                {request.text.length.toLocaleString()}{" "}
                characters
              </span>
            </div>

            <textarea
              aria-label="Text to rewrite"
              value={request.text}
              onChange={(event) =>
                setRequest((current) => ({
                  ...current,
                  text: event.target.value
                }))
              }
              required
              maxLength={20000}
            />

            <div className="control-row">
              <label>
                Rewrite intensity
                <select
                  value={request.intensity}
                  onChange={(event) =>
                    setRequest((current) => ({
                      ...current,
                      intensity: event.target
                        .value as RewriteRequest["intensity"]
                    }))
                  }
                >
                  <option value="light_edit">
                    Light edit
                  </option>
                  <option value="natural_rewrite">
                    Natural rewrite
                  </option>
                  <option value="deep_reconstruction">
                    Deep reconstruction
                  </option>
                </select>
              </label>

              <label>
                Document type
                <select
                  value={request.document_type}
                  onChange={(event) =>
                    setRequest((current) => ({
                      ...current,
                      document_type: event.target
                        .value as RewriteRequest["document_type"]
                    }))
                  }
                >
                  <option value="general">
                    General
                  </option>
                  <option value="professional_email">
                    Professional email
                  </option>
                  <option value="interview_answer">
                    Interview answer
                  </option>
                  <option value="technical_document">
                    Technical document
                  </option>
                  <option value="social_post">
                    Social post
                  </option>
                </select>
              </label>
            </div>

            {canCustomizeClaimLock && (
              <section className="enterprise-claim-lock-request-customization">
                <div className="enterprise-claim-lock-request-customization__header">
                  <div>
                    <p className="eyebrow">
                      Optional Claim Lock
                    </p>
                    <strong>
                      Request-specific protection
                    </strong>
                    <span>
                      Workspace policy remains
                      server-resolved and is not
                      copied into this request.
                    </span>
                  </div>

                  <button
                    type="button"
                    className="secondary-action"
                    disabled={isSubmitting}
                    onClick={() =>
                      setClaimLockTerms(
                        (current) => [
                          ...current,
                          {
                            text: "",
                            case_sensitive: true
                          }
                        ]
                      )
                    }
                  >
                    Add protected term
                  </button>
                </div>

                <label>
                  Request enforcement mode
                  <select
                    value={claimLockMode}
                    disabled={isSubmitting}
                    onChange={(event) =>
                      setClaimLockMode(
                        event.target.value as
                          RequestClaimLockMode
                      )
                    }
                  >
                    <option value="">
                      Server-determined
                    </option>
                    <option value="strict">
                      Strict
                    </option>
                    <option value="audit_only">
                      Audit only
                    </option>
                  </select>
                </label>

                {claimLockTerms.length > 0 && (
                  <div className="enterprise-claim-lock-request-term-list">
                    {claimLockTerms.map(
                      (term, index) => (
                        <div
                          className="enterprise-claim-lock-request-term-row"
                          key={index}
                        >
                          <label>
                            Protected term
                            <input
                              type="text"
                              value={term.text}
                              disabled={isSubmitting}
                              maxLength={1000}
                              onChange={(event) =>
                                setClaimLockTerms(
                                  (current) =>
                                    current.map(
                                      (
                                        currentTerm,
                                        currentIndex
                                      ) =>
                                        currentIndex ===
                                        index
                                          ? {
                                              ...currentTerm,
                                              text:
                                                event
                                                  .target
                                                  .value
                                            }
                                          : currentTerm
                                    )
                                )
                              }
                            />
                          </label>

                          <label className="enterprise-claim-lock-request-checkbox">
                            <input
                              type="checkbox"
                              checked={
                                term.case_sensitive
                              }
                              disabled={isSubmitting}
                              onChange={(event) =>
                                setClaimLockTerms(
                                  (current) =>
                                    current.map(
                                      (
                                        currentTerm,
                                        currentIndex
                                      ) =>
                                        currentIndex ===
                                        index
                                          ? {
                                              ...currentTerm,
                                              case_sensitive:
                                                event
                                                  .target
                                                  .checked
                                            }
                                          : currentTerm
                                    )
                                )
                              }
                            />
                            Case sensitive
                          </label>

                          <button
                            type="button"
                            className="secondary-action"
                            disabled={isSubmitting}
                            onClick={() =>
                              setClaimLockTerms(
                                (current) =>
                                  current.filter(
                                    (_, currentIndex) =>
                                      currentIndex !==
                                      index
                                  )
                              )
                            }
                          >
                            Remove
                          </button>
                        </div>
                      )
                    )}
                  </div>
                )}
              </section>
            )}

            <button
              className="primary-action"
              disabled={
                isSubmitting ||
                request.text.trim() === ""
              }
              type="submit"
            >
              {isSubmitting
                ? "Evaluating rewrite need..."
                : isResultStale
                  ? "Run again with updated inputs"
                  : "Analyze and rewrite"}
            </button>

            {isResultStale && (
              <div
                className="stale-notice stale-notice--editor"
                role="status"
              >
                Inputs changed. Run again to refresh the
                displayed result.
              </div>
            )}

            {error && (
              <div
                className="error-banner"
                role="alert"
              >
                {error}
              </div>
            )}
          </form>

          <section className="result-column result-column--governed">
            <div className="workspace-panel-label">
              <span>Governed result</span>
              <strong>
                Decision, output, verification, and evidence
              </strong>
            </div>
            {response && submittedResult ? (
              <>
                {isResultStale && (
                  <section
                    className="stale-notice stale-notice--result"
                    aria-labelledby="stale-result-title"
                  >
                    <div>
                      <strong id="stale-result-title">
                        Displayed result is from an earlier
                        submission
                      </strong>
                      <span>
                        Your current text or controls have
                        changed. The result below has not
                        been regenerated.
                      </span>
                    </div>

                    <span className="stale-badge">
                      Refresh required
                    </span>
                  </section>
                )}

                <section
                  className="submission-context"
                  aria-label="Submitted request settings"
                >
                  <div>
                    <p className="eyebrow">
                      Processed as
                    </p>
                    <strong>
                      {
                        DOCUMENT_TYPE_LABELS[
                          submittedResult.request
                            .document_type
                        ]
                      }
                    </strong>
                    <span aria-hidden="true">·</span>
                    <strong>
                      {
                        INTENSITY_LABELS[
                          submittedResult.request.intensity
                        ]
                      }
                    </strong>
                  </div>

                  <span className="submission-context__trace">
                    Trace {response.trace_id}
                  </span>
                </section>

                <RewriteDecisionCard
                  response={response}
                />

                <article className="output-card">
                  <div className="card-header">
                    <div>
                      <p className="eyebrow">Result</p>
                      <h2>Rewritten text</h2>
                    </div>

                    <div className="output-card__actions">
                      <span>
                        {response.rewritten_text.length}{" "}
                        characters
                      </span>

                      <button
                        className="secondary-action"
                        type="button"
                        onClick={handleCopyResult}
                      >
                        {copyState === "copied"
                          ? "Copied"
                          : copyState === "failed"
                            ? "Copy failed"
                            : "Copy result"}
                      </button>
                    </div>
                  </div>

                  <p className="rewritten-text">
                    {response.rewritten_text}
                  </p>

                  <div
                    className="copy-status"
                    aria-live="polite"
                  >
                    {copyState === "copied" &&
                      "Rewritten text copied to the clipboard."}
                    {copyState === "failed" &&
                      "The browser could not copy the result. Select the text and copy it manually."}
                  </div>
                </article>

                <div id="audit">
                  <RewriteAuditDetails
                    response={response}
                  />
                </div>

                <ClaimLockExecutionEvidence
                  evidence={
                    submittedResult
                      .response
                      .claim_lock
                  }
                />
              </>
            ) : (
              <section className="empty-state">
                <div className="empty-state__icon">
                  Aa
                </div>
                <h2>Ready to evaluate your text</h2>
                <p>
                  The platform will first determine whether
                  your text needs no change, a light cleanup,
                  or a full AI rewrite.
                </p>
              </section>
            )}
          </section>
        </section>
      </main>
  );
}
