import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  WorkspaceEvaluationEvidenceError,
  fetchWorkspaceEvaluationEvidenceList,
  type WorkspaceEvaluationEvidenceRecord
} from "../api/evaluationEvidence";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface EvalOpsPageProps {
  accessContext: EnterpriseAccessContextState;
}

type EvalOpsLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "denied"
  | "error";

const EVALOPS_READ_PERMISSION =
  "evaluation.read";

function formatTimestamp(
  value: string
): string {
  const date = new Date(
    value
  );

  return Number.isNaN(
    date.getTime()
  )
    ? value
    : date.toLocaleString();
}

function displayStatus(
  value: string
): string {
  return value
    .split("_")
    .filter(Boolean)
    .map(
      (segment) =>
        segment.charAt(0).toUpperCase() +
        segment.slice(1)
    )
    .join(" ");
}

export default function EvalOpsPage({
  accessContext
}: EvalOpsPageProps) {
  const [records, setRecords] =
    useState<
      WorkspaceEvaluationEvidenceRecord[]
    >([]);

  const [
    selectedBindingId,
    setSelectedBindingId
  ] = useState<string | null>(
    null
  );

  const [loadState, setLoadState] =
    useState<EvalOpsLoadState>(
      "idle"
    );

  const [message, setMessage] =
    useState<string | null>(
      null
    );

  const [
    refreshSequence,
    setRefreshSequence
  ] = useState(
    0
  );

  const hasReadPermission =
    accessContext.context?.permissions.includes(
      EVALOPS_READ_PERMISSION
    ) ?? false;

  const canQuery =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null &&
    hasReadPermission;

  const loadEvidence = useCallback(
    async (
      signal: AbortSignal
    ) => {
      if (!canQuery) {
        setRecords([]);
        setSelectedBindingId(null);
        setLoadState("idle");
        setMessage(null);
        return;
      }

      const workspaceId =
        accessContext.workspaceId;

      const userId =
        accessContext.userId;

      if (
        workspaceId === null ||
        userId === null
      ) {
        return;
      }

      setLoadState(
        "loading"
      );

      setMessage(
        "Loading authorized workspace evaluation evidence."
      );

      try {
        const next =
          await fetchWorkspaceEvaluationEvidenceList({
            workspaceId,
            userId,
            limit: 50,
            signal
          });

        if (
          signal.aborted
        ) {
          return;
        }

        setRecords(
          next.records
        );

        setSelectedBindingId(
          (current) => {
            if (
              current !== null &&
              next.records.some(
                (record) =>
                  record.binding_id ===
                  current
              )
            ) {
              return current;
            }

            return (
              next.records[0]
                ?.binding_id ??
              null
            );
          }
        );

        setLoadState(
          "ready"
        );

        setMessage(
          "Evaluation evidence loaded through the workspace-authorized read contract."
        );
      } catch (
        error: unknown
      ) {
        if (
          signal.aborted
        ) {
          return;
        }

        setRecords([]);
        setSelectedBindingId(null);

        if (
          error instanceof
            WorkspaceEvaluationEvidenceError
        ) {
          setLoadState(
            error.status === 403
              ? "denied"
              : "error"
          );

          setMessage(
            error.detail
          );

          return;
        }

        setLoadState(
          "error"
        );

        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load evaluation evidence."
        );
      }
    },
    [
      accessContext.workspaceId,
      accessContext.userId,
      canQuery
    ]
  );

  useEffect(
    () => {
      const controller =
        new AbortController();

      void loadEvidence(
        controller.signal
      );

      return () => {
        controller.abort();
      };
    },
    [
      loadEvidence,
      refreshSequence
    ]
  );

  const selected =
    useMemo(
      () =>
        records.find(
          (record) =>
            record.binding_id ===
            selectedBindingId
        ) ?? null,
      [
        records,
        selectedBindingId
      ]
    );

  const selectedGate =
    selected?.gate_result ??
    null;

  let stateTitle =
    "Workspace context required";

  let stateDetail =
    "Connect a canonical workspace and user context to view evaluation evidence.";

  if (
    accessContext.status ===
    "loading"
  ) {
    stateTitle =
      "Resolving workspace context";

    stateDetail =
      "EvalOps evidence will load after canonical access context resolution.";
  } else if (
    accessContext.status ===
    "denied"
  ) {
    stateTitle =
      "Workspace access denied";

    stateDetail =
      accessContext.message ??
      "The server denied access to the requested workspace.";
  } else if (
    accessContext.status ===
    "invalid"
  ) {
    stateTitle =
      "Workspace configuration required";

    stateDetail =
      accessContext.message ??
      "Both workspace_id and user_id are required.";
  } else if (
    accessContext.status ===
    "error"
  ) {
    stateTitle =
      "Workspace context unavailable";

    stateDetail =
      accessContext.message ??
      "The canonical workspace context could not be resolved.";
  } else if (
    accessContext.status ===
      "connected" &&
    !hasReadPermission
  ) {
    stateTitle =
      "Evaluation evidence not granted";

    stateDetail =
      "The resolved workspace access context does not include evaluation.read.";
  } else if (
    loadState ===
    "loading"
  ) {
    stateTitle =
      "Loading evaluation evidence";

    stateDetail =
      "Requesting workspace-authorized evaluation evidence.";
  } else if (
    loadState ===
    "denied"
  ) {
    stateTitle =
      "Evaluation evidence access denied";

    stateDetail =
      message ??
      "The evaluation evidence endpoint denied this workspace request.";
  } else if (
    loadState ===
    "error"
  ) {
    stateTitle =
      "Evaluation evidence unavailable";

    stateDetail =
      message ??
      "Workspace evaluation evidence could not be loaded.";
  }

  const ready =
    loadState ===
    "ready";

  return (
    <div className="enterprise-page">
      <section className="enterprise-hero">
        <div>
          <p className="enterprise-eyebrow">
            Governance · EvalOps
          </p>

          <h1>
            Evaluation evidence
          </h1>

          <p className="enterprise-hero__description">
            Read-only workspace visibility into
            recorded evaluation runs and quality
            gates. This surface presents authorized
            evidence only; evaluation execution and
            management authority remain unavailable.
          </p>
        </div>

        <div className="enterprise-hero__actions">
          <button
            type="button"
            className="enterprise-secondary-button"
            disabled={
              !canQuery ||
              loadState === "loading"
            }
            onClick={() =>
              setRefreshSequence(
                (sequence) =>
                  sequence + 1
              )
            }
          >
            Refresh evidence
          </button>

          <span className="enterprise-release-badge">
            Workspace EvalOps · read only
          </span>
        </div>
      </section>

      <section className="enterprise-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Authorized evidence
            </p>

            <h2>
              Recorded evaluation evidence
            </h2>
          </div>

          <p>
            Operation lifecycle, evaluation outcome,
            and gate decision remain separate facts.
          </p>
        </div>

        {!ready ? (
          <div className="enterprise-placeholder__boundary">
            <strong>
              {stateTitle}
            </strong>

            <p>
              {stateDetail}
            </p>
          </div>
        ) : records.length === 0 ? (
          <div className="enterprise-placeholder__boundary">
            <strong>
              No evaluation evidence
            </strong>

            <p>
              No recorded evaluation evidence is
              currently visible for this workspace.
            </p>
          </div>
        ) : (
          <>
            <p>
              <strong>
                {records.length}
              </strong>
              {" "}
              evidence records visible through the
              authorized workspace read contract.
            </p>

            <div className="enterprise-analytics-operation-grid">
              {records.map(
                (record) => (
                  <button
                    type="button"
                    className="enterprise-analytics-operation"
                    key={record.binding_id}
                    aria-pressed={
                      selectedBindingId ===
                      record.binding_id
                    }
                    onClick={() =>
                      setSelectedBindingId(
                        record.binding_id
                      )
                    }
                  >
                    <div className="enterprise-analytics-operation__header">
                      <span>
                        {record.binding_id}
                      </span>

                      <strong>
                        {displayStatus(
                          record.operation_status
                        )}
                      </strong>
                    </div>

                    <dl>
                      <div>
                        <dt>
                          Operation
                        </dt>
                        <dd>
                          {record.operation_id}
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Evidence kind
                        </dt>
                        <dd>
                          {displayStatus(
                            record.evidence_kind
                          )}
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Run outcome
                        </dt>
                        <dd>
                          {displayStatus(
                            record.run.outcome
                          )}
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Recorded
                        </dt>
                        <dd>
                          {formatTimestamp(
                            record.recorded_at
                          )}
                        </dd>
                      </div>
                    </dl>
                  </button>
                )
              )}
            </div>
          </>
        )}
      </section>

      {selected !== null && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Selected evidence
              </p>

              <h2>
                {selected.binding_id}
              </h2>
            </div>

            <p>
              A succeeded operation can contain a
              failed evaluation run because lifecycle
              completion does not imply quality
              success.
            </p>
          </div>

          <div className="enterprise-analytics-metric-grid">
            <article className="enterprise-analytics-metric">
              <span>
                Operation ID
              </span>
              <strong>
                {selected.operation_id}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Operation lifecycle
              </span>
              <strong>
                {displayStatus(
                  selected.operation_status
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Evidence kind
              </span>
              <strong>
                {displayStatus(
                  selected.evidence_kind
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Run ID
              </span>
              <strong>
                {
                  selected.run
                    .identity.run_id
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Run outcome
              </span>
              <strong>
                {displayStatus(
                  selected.run.outcome
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Dataset ID
              </span>
              <strong>
                {
                  selected.run
                    .identity.dataset
                    .dataset_id
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Dataset version
              </span>
              <strong>
                {
                  selected.run
                    .identity.dataset
                    .dataset_version
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Target ID
              </span>
              <strong>
                {
                  selected.run
                    .identity.target_id
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Evaluated cases
              </span>
              <strong>
                {
                  selected.run
                    .evaluated_case_count
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Failed cases
              </span>
              <strong>
                {
                  selected.run
                    .failed_case_count
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Recorded
              </span>
              <strong>
                {formatTimestamp(
                  selected.recorded_at
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Observed
              </span>
              <strong>
                {formatTimestamp(
                  selected.observed_at
                )}
              </strong>
            </article>
          </div>

          {selected.run.failure_reason !== null && (
            <div className="enterprise-placeholder__boundary">
              <strong>
                Evaluation failure reason
              </strong>

              <p>
                {selected.run.failure_reason}
              </p>
            </div>
          )}

          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Run metrics
              </p>

              <h2>
                Recorded metric results
              </h2>
            </div>
          </div>

          <div className="enterprise-analytics-metric-grid">
            {selected.run.metric_results.map(
              (metric) => (
                <article
                  className="enterprise-analytics-metric"
                  key={metric.metric}
                >
                  <span>
                    {displayStatus(
                      metric.metric
                    )}
                  </span>

                  <strong>
                    {metric.value}
                  </strong>
                </article>
              )
            )}
          </div>

          {selectedGate !== null && (
            <>
              <div className="enterprise-section__heading">
                <div>
                  <p className="enterprise-eyebrow">
                    Quality gate
                  </p>

                  <h2>
                    {selectedGate.gate.gate_id}
                  </h2>
                </div>

                <p>
                  Gate decision:{" "}
                  <strong>
                    {displayStatus(
                      selectedGate.decision
                    )}
                  </strong>
                </p>
              </div>

              <div className="enterprise-analytics-operation-grid">
                {selectedGate.gate.thresholds.map(
                  (threshold) => {
                    const result =
                      selectedGate.metric_results.find(
                        (candidate) =>
                          candidate.metric ===
                          threshold.metric
                      );

                    return (
                      <article
                        className="enterprise-analytics-operation"
                        key={threshold.metric}
                      >
                        <div className="enterprise-analytics-operation__header">
                          <span>
                            {displayStatus(
                              threshold.metric
                            )}
                          </span>

                          <strong>
                            {result?.value ?? "Unavailable"}
                          </strong>
                        </div>

                        <dl>
                          <div>
                            <dt>
                              Comparator
                            </dt>
                            <dd>
                              {displayStatus(
                                threshold.comparator
                              )}
                            </dd>
                          </div>

                          <div>
                            <dt>
                              Threshold
                            </dt>
                            <dd>
                              {threshold.threshold}
                            </dd>
                          </div>
                        </dl>
                      </article>
                    );
                  }
                )}
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}
