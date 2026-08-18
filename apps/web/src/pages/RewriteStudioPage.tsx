import {
  FormEvent,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  submitRewrite,
  type RewriteRequest,
  type RewriteResponse
} from "../api/rewrite";
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

interface SubmittedResult {
  request: RewriteRequest;
  response: RewriteResponse;
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

export default function RewriteStudioPage() {
  const [request, setRequest] =
    useState<RewriteRequest>(INITIAL_REQUEST);
  const [submittedResult, setSubmittedResult] =
    useState<SubmittedResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copyState, setCopyState] = useState<
    "idle" | "copied" | "failed"
  >("idle");

  const response = submittedResult?.response ?? null;

  const isResultStale = useMemo(() => {
    if (submittedResult === null) {
      return false;
    }

    return !requestsMatch(
      request,
      submittedResult.request
    );
  }, [request, submittedResult]);

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

    try {
      const result = await submitRewrite(
        requestSnapshot
      );

      setSubmittedResult({
        request: requestSnapshot,
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


      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">
              Meaning-preserving rewriting
            </p>
            <h1>Humanize your AI text</h1>
            <p>
              Improve tone and naturalness without losing
              protected facts, numbers, dates, or intent.
            </p>
          </div>

          <div className="system-badge">
            Governed workflow
          </div>
        </header>

        <section className="studio-grid" id="studio">
          <form
            className="editor-card"
            onSubmit={handleSubmit}
          >
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

          <section className="result-column">
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
