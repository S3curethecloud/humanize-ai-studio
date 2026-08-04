import { FormEvent, useState } from "react";

import {
  submitRewrite,
  type RewriteRequest,
  type RewriteResponse
} from "./api/rewrite";
import { RewriteAuditDetails } from "./components/RewriteAuditDetails";
import { RewriteDecisionCard } from "./components/RewriteDecisionCard";

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

export default function App() {
  const [request, setRequest] =
    useState<RewriteRequest>(INITIAL_REQUEST);
  const [response, setResponse] =
    useState<RewriteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError(null);
    setIsSubmitting(true);

    try {
      const result = await submitRewrite(request);
      setResponse(result);
    } catch (caughtError) {
      setResponse(null);
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "The rewrite request failed."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">H</span>
          <div>
            <strong>Humanize AI</strong>
            <span>Studio</span>
          </div>
        </div>

        <nav aria-label="Primary navigation">
          <a className="nav-item nav-item--active" href="#studio">
            Rewrite Studio
          </a>
          <a className="nav-item" href="#audit">
            Audit Evidence
          </a>
        </nav>

        <div className="sidebar__status">
          <span className="status-dot" />
          Evaluation controls active
        </div>
      </aside>

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
                {request.text.length.toLocaleString()} characters
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
                  <option value="general">General</option>
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
                isSubmitting || request.text.trim() === ""
              }
              type="submit"
            >
              {isSubmitting
                ? "Evaluating rewrite need..."
                : "Analyze and rewrite"}
            </button>

            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}
          </form>

          <section className="result-column">
            {response ? (
              <>
                <RewriteDecisionCard response={response} />

                <article className="output-card">
                  <div className="card-header">
                    <div>
                      <p className="eyebrow">Result</p>
                      <h2>Rewritten text</h2>
                    </div>

                    <span>
                      {
                        response.rewritten_text.length
                      }{" "}
                      characters
                    </span>
                  </div>

                  <p className="rewritten-text">
                    {response.rewritten_text}
                  </p>
                </article>

                <div id="audit">
                  <RewriteAuditDetails
                    response={response}
                  />
                </div>
              </>
            ) : (
              <section className="empty-state">
                <div className="empty-state__icon">Aa</div>
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
    </div>
  );
}
