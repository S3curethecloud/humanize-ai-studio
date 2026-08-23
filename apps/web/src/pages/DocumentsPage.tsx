import {
  useState
} from "react";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  submitLongDocumentRewrite,
  type LongDocumentRewriteResponse
} from "../api/longDocument";

interface DocumentsPageProps {
  accessContext: EnterpriseAccessContextState;
}

const DEFAULT_TEXT = `Executive Summary

Our engineering team worked closely with business stakeholders to complete the migration within 30 days. The team documented the production handoff and defined operational ownership.

Architecture

The solution uses governed API integration patterns, explicit identity propagation, and controlled provider execution. Security boundaries remain separate from model behavior.

Operational Handoff

Production readiness included testing, observability, runbook documentation, and stakeholder handoff.`;

export default function DocumentsPage({
  accessContext
}: DocumentsPageProps) {
  const [text, setText] =
    useState(DEFAULT_TEXT);

  const [intensity, setIntensity] =
    useState<
      "light_edit" |
      "natural_rewrite" |
      "deep_reconstruction"
    >("natural_rewrite");

  const [result, setResult] =
    useState<LongDocumentRewriteResponse | null>(
      null
    );

  const [message, setMessage] =
    useState<string | null>(null);

  const [busy, setBusy] =
    useState(false);

  const canExecute =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  async function handleRewrite() {
    if (
      !canExecute ||
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      setMessage(
        "Canonical workspace access context is required."
      );
      return;
    }

    if (!text.trim()) {
      setMessage(
        "Document text is required."
      );
      return;
    }

    setBusy(true);
    setMessage(
      "Executing governed long-document rewrite."
    );

    try {
      const next =
        await submitLongDocumentRewrite(
          accessContext.workspaceId,
          accessContext.userId,
          {
            text: text.trim(),
            document_type:
              "technical_document",
            audience:
              "enterprise stakeholders",
            tone:
              "clear, natural, and professional",
            intensity,
            preserve_numbers: true,
            preserve_dates: true
          }
        );

      setResult(next);
      setMessage(
        "Long-document reconstruction completed."
      );
    } catch (error) {
      setResult(null);
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to execute long-document rewrite."
      );
    } finally {
      setBusy(false);
    }
  }

  if (!canExecute) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Documents unavailable</h1>
            <p>
              Canonical workspace access context is
              required before long-document rewrite
              execution.
            </p>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="enterprise-page">
      <section className="enterprise-analytics-hero">
        <div>
          <p className="enterprise-eyebrow">
            Work · Documents
          </p>

          <h1>Long Document Workspace</h1>

          <p className="enterprise-hero__description">
            Execute governed section-aware document
            reconstruction while preserving ordered
            structure and protected factual content.
          </p>
        </div>
      </section>

      {message && (
        <section className="enterprise-analytics-state">
          <div>
            <p>{message}</p>
          </div>
        </section>
      )}

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Source document
            </p>
            <h2>Document content</h2>
          </div>
        </div>

        <div className="source-workspace">
          <label>
            Rewrite intensity
            <select
              value={intensity}
              onChange={(event) =>
                setIntensity(
                  event.target.value as
                    typeof intensity
                )
              }
              disabled={busy}
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
            Document text
            <textarea
              rows={18}
              value={text}
              onChange={(event) =>
                setText(event.target.value)
              }
              disabled={busy}
            />
          </label>

          <button
            type="button"
            className="enterprise-secondary-button"
            disabled={busy}
            onClick={() =>
              void handleRewrite()
            }
          >
            Rewrite long document
          </button>
        </div>
      </section>

      {result && (
        <>
          <section className="enterprise-dashboard-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Reconstruction
                </p>
                <h2>
                  Governed document result
                </h2>
              </div>

              <p>
                {
                  result.reconstruction
                    .section_results.length
                } sections
              </p>
            </div>

            <div className="source-workspace">
              <h3>Reconstructed text</h3>
              <p>
                {
                  result.reconstruction
                    .reconstructed_text
                }
              </p>
            </div>
          </section>

          <section className="enterprise-dashboard-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Section evidence
                </p>
                <h2>
                  Rewrite dispositions
                </h2>
              </div>
            </div>

            <div className="enterprise-analytics-operation-grid">
              {result.reconstruction.section_results.map(
                (section) => (
                  <article
                    className="enterprise-analytics-operation"
                    key={section.section_id}
                  >
                    <div className="enterprise-analytics-operation__header">
                      <span>
                        Section {section.ordinal}
                      </span>
                      <strong>
                        {section.disposition}
                      </strong>
                    </div>

                    <dl>
                      <div>
                        <dt>Source characters</dt>
                        <dd>
                          {
                            section.source_text
                              .length
                          }
                        </dd>
                      </div>

                      <div>
                        <dt>Output characters</dt>
                        <dd>
                          {
                            section.rewritten_text
                              .length
                          }
                        </dd>
                      </div>
                    </dl>
                  </article>
                )
              )}
            </div>
          </section>

          <section className="enterprise-dashboard-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Audit linkage
                </p>
                <h2>
                  Long-document audit
                </h2>
              </div>
            </div>

            <div className="enterprise-analytics-metric-grid">
              <article className="enterprise-analytics-metric">
                <span>Audit ID</span>
                <strong>
                  {result.audit.audit_id}
                </strong>
              </article>

              <article className="enterprise-analytics-metric">
                <span>Workspace</span>
                <strong>
                  {result.audit.workspace_id}
                </strong>
              </article>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
