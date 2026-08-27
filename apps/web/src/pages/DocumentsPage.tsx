import {
  useMemo,
  useState
} from "react";

import type {
  ClaimLockEnforcementMode,
  ClaimLockRequestCustomization
} from "../api/claimLock";
import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  submitLongDocumentRewrite,
  type LongDocumentRewriteResponse
} from "../api/longDocument";
import ClaimLockExecutionEvidence from "../components/ClaimLockExecutionEvidence";

interface DocumentsPageProps {
  accessContext: EnterpriseAccessContextState;
}

const DEFAULT_TEXT = `Executive Summary

Our engineering team worked closely with business stakeholders to complete the migration within 30 days. The team documented the production handoff and defined operational ownership.

Architecture

The solution uses governed API integration patterns, explicit identity propagation, and controlled provider execution. Security boundaries remain separate from model behavior.

Operational Handoff

Production readiness included testing, observability, runbook documentation, and stakeholder handoff.`;

type DocumentIntensity =
  | "light_edit"
  | "natural_rewrite"
  | "deep_reconstruction";

type RequestClaimLockMode =
  | ""
  | ClaimLockEnforcementMode;

interface RequestClaimLockTermDraft {
  text: string;
  case_sensitive: boolean;
}

interface SubmittedDocumentResult {
  text: string;
  intensity: DocumentIntensity;
  claimLock?: ClaimLockRequestCustomization;
  response: LongDocumentRewriteResponse;
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

export default function DocumentsPage({
  accessContext
}: DocumentsPageProps) {
  const [text, setText] =
    useState(DEFAULT_TEXT);

  const [intensity, setIntensity] =
    useState<DocumentIntensity>(
      "natural_rewrite"
    );

  const [claimLockMode, setClaimLockMode] =
    useState<RequestClaimLockMode>("");

  const [claimLockTerms, setClaimLockTerms] =
    useState<RequestClaimLockTermDraft[]>([]);

  const [submittedResult, setSubmittedResult] =
    useState<SubmittedDocumentResult | null>(
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

  const result =
    submittedResult?.response ?? null;

  const isResultStale =
    useMemo(
      () => {
        if (submittedResult === null) {
          return false;
        }

        return (
          text !== submittedResult.text ||
          intensity !==
            submittedResult.intensity ||
          !customizationsMatch(
            currentClaimLockCustomization,
            submittedResult.claimLock
          )
        );
      },
      [
        currentClaimLockCustomization,
        intensity,
        submittedResult,
        text
      ]
    );

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

    const textSnapshot = text;
    const intensitySnapshot = intensity;
    const claimLockSnapshot =
      cloneClaimLockCustomization(
        currentClaimLockCustomization
      );

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
            text: textSnapshot.trim(),
            document_type:
              "technical_document",
            audience:
              "enterprise stakeholders",
            tone:
              "clear, natural, and professional",
            intensity: intensitySnapshot,
            preserve_numbers: true,
            preserve_dates: true
          },
          claimLockSnapshot
        );

      setSubmittedResult({
        text: textSnapshot,
        intensity: intensitySnapshot,
        claimLock: claimLockSnapshot,
        response: next
      });
      setMessage(
        "Long-document reconstruction completed."
      );
    } catch (error) {
      setSubmittedResult(null);
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

          {canCustomizeClaimLock && (
            <section className="enterprise-claim-lock-request-customization">
              <div className="enterprise-claim-lock-request-customization__header">
                <div>
                  <p className="enterprise-eyebrow">
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
                  className="enterprise-secondary-button"
                  disabled={busy}
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
                  disabled={busy}
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
                            maxLength={1000}
                            value={term.text}
                            disabled={busy}
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
                            disabled={busy}
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
                          className="enterprise-secondary-button"
                          disabled={busy}
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
            type="button"
            className="enterprise-secondary-button"
            disabled={busy}
            onClick={() =>
              void handleRewrite()
            }
          >
            {isResultStale
              ? "Rewrite again with updated inputs"
              : "Rewrite long document"}
          </button>
        </div>
      </section>

      {result && submittedResult && (
        <>
          {isResultStale && (
            <section className="enterprise-analytics-state enterprise-claim-lock-execution-stale">
              <div>
                <h2>
                  Displayed document result is stale
                </h2>
                <p>
                  Document text, rewrite intensity, or
                  request Claim Lock controls changed
                  after this execution. Run again before
                  treating the result or evidence as
                  current.
                </p>
              </div>
            </section>
          )}

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

          <ClaimLockExecutionEvidence
            evidence={result.claim_lock}
          />
        </>
      )}
    </div>
  );
}
