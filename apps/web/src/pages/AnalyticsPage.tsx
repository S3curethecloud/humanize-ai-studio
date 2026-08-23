import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  WorkspaceAnalyticsError,
  fetchWorkspaceAnalytics,
  type AnalyticsOperation,
  type AnalyticsOperationBucket,
  type WorkspaceAnalyticsSnapshot
} from "../api/analytics";
import {
  type EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface AnalyticsPageProps {
  accessContext: EnterpriseAccessContextState;
}

type AnalyticsLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "denied"
  | "window-limit"
  | "error";

const WINDOW_HOURS = 24;

const OPERATION_LABELS: Record<
  AnalyticsOperation,
  string
> = {
  single_rewrite: "Single rewrite",
  multi_candidate_rewrite:
    "Multi-candidate rewrite",
  long_document_rewrite:
    "Long-document rewrite"
};

function formatNumber(
  value: number
): string {
  return new Intl.NumberFormat().format(value);
}

function formatDuration(
  durationMs: number
): string {
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }

  return `${(durationMs / 1000).toFixed(2)} s`;
}

function formatTimestamp(
  value: string
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function operationFor(
  snapshot: WorkspaceAnalyticsSnapshot,
  operation: AnalyticsOperation
): AnalyticsOperationBucket | undefined {
  return snapshot.operations.find(
    (bucket) =>
      bucket.operation === operation
  );
}

export default function AnalyticsPage({
  accessContext
}: AnalyticsPageProps) {
  const [snapshot, setSnapshot] =
    useState<WorkspaceAnalyticsSnapshot | null>(
      null
    );

  const [loadState, setLoadState] =
    useState<AnalyticsLoadState>("idle");

  const [message, setMessage] =
    useState<string | null>(null);

  const [refreshSequence, setRefreshSequence] =
    useState(0);

  const canQuery =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  const loadAnalytics = useCallback(
    async (
      signal: AbortSignal
    ) => {
      if (!canQuery) {
        setSnapshot(null);
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

      const periodEnd = new Date();
      const periodStart = new Date(
        periodEnd.getTime() -
          WINDOW_HOURS * 60 * 60 * 1000
      );

      setLoadState("loading");
      setMessage(
        "Loading authoritative workspace analytics."
      );

      try {
        const nextSnapshot =
          await fetchWorkspaceAnalytics({
            workspaceId,
            userId,
            periodStart,
            periodEnd,
            signal
          });

        if (signal.aborted) {
          return;
        }

        setSnapshot(nextSnapshot);
        setLoadState("ready");
        setMessage(
          "Workspace analytics loaded from persistent observability evidence."
        );
      } catch (error: unknown) {
        if (signal.aborted) {
          return;
        }

        setSnapshot(null);

        if (
          error instanceof
            WorkspaceAnalyticsError
        ) {
          if (error.status === 403) {
            setLoadState("denied");
          } else if (error.status === 409) {
            setLoadState("window-limit");
          } else {
            setLoadState("error");
          }

          setMessage(error.detail);
          return;
        }

        setLoadState("error");
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load workspace analytics."
        );
      }
    },
    [
      accessContext.workspaceId,
      accessContext.userId,
      canQuery
    ]
  );

  useEffect(() => {
    const controller =
      new AbortController();

    void loadAnalytics(
      controller.signal
    );

    return () => {
      controller.abort();
    };
  }, [
    loadAnalytics,
    refreshSequence
  ]);

  const summary = useMemo(
    () => [
      {
        label: "Events",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot.event_count
              )
      },
      {
        label: "Succeeded",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot.succeeded_count
              )
      },
      {
        label: "Controlled failures",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot
                  .controlled_failure_count
              )
      },
      {
        label: "System failures",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot.system_failure_count
              )
      }
    ],
    [snapshot]
  );

  const execution = useMemo(
    () => [
      {
        label: "Provider executions",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot
                  .total_provider_executions
              )
      },
      {
        label: "Fallbacks",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot.total_fallbacks
              )
      },
      {
        label: "Total tokens",
        value:
          snapshot === null
            ? "—"
            : formatNumber(
                snapshot.total_tokens
              )
      },
      {
        label: "Total duration",
        value:
          snapshot === null
            ? "—"
            : formatDuration(
                snapshot.total_duration_ms
              )
      }
    ],
    [snapshot]
  );

  const operationOrder: AnalyticsOperation[] =
    [
      "single_rewrite",
      "multi_candidate_rewrite",
      "long_document_rewrite"
    ];

  let stateTitle =
    "Workspace context required";

  let stateDetail =
    "Connect a canonical workspace and user context to query operational analytics.";

  if (
    accessContext.status === "loading"
  ) {
    stateTitle =
      "Resolving workspace context";
    stateDetail =
      "Analytics will load after the canonical access context is resolved.";
  } else if (
    accessContext.status === "denied"
  ) {
    stateTitle = "Workspace access denied";
    stateDetail =
      accessContext.message ??
      "The server denied access to the requested workspace.";
  } else if (
    accessContext.status === "invalid"
  ) {
    stateTitle =
      "Workspace configuration required";
    stateDetail =
      accessContext.message ??
      "Both workspace_id and user_id are required.";
  } else if (
    accessContext.status === "error"
  ) {
    stateTitle =
      "Workspace context unavailable";
    stateDetail =
      accessContext.message ??
      "The canonical workspace access context could not be resolved.";
  } else if (
    loadState === "loading"
  ) {
    stateTitle =
      "Loading workspace analytics";
    stateDetail =
      "Querying the most recent 24-hour observability window.";
  } else if (
    loadState === "denied"
  ) {
    stateTitle =
      "Analytics access denied";
    stateDetail =
      message ??
      "The analytics endpoint denied this workspace request.";
  } else if (
    loadState === "window-limit"
  ) {
    stateTitle =
      "Analytics window is too broad";
    stateDetail =
      message ??
      "Narrow the analytics query window.";
  } else if (
    loadState === "error"
  ) {
    stateTitle =
      "Analytics unavailable";
    stateDetail =
      message ??
      "Workspace analytics could not be loaded.";
  }

  const showState =
    snapshot === null;

  const isEmpty =
    snapshot !== null &&
    snapshot.event_count === 0;

  return (
    <div className="enterprise-page enterprise-analytics">
      <section className="enterprise-analytics-hero">
        <div>
          <p className="enterprise-eyebrow">
            Operations · Analytics
          </p>

          <h1>Workspace operational analytics</h1>

          <p className="enterprise-hero__description">
            Review workspace-scoped observability
            evidence for governed rewrite operations.
            Metrics reflect recorded execution only;
            they do not redefine routing, provider,
            or policy authority.
          </p>
        </div>

        <div className="enterprise-analytics-hero__actions">
          <span className="enterprise-release-badge">
            24-hour window
          </span>

          <button
            className="enterprise-secondary-button"
            type="button"
            onClick={() =>
              setRefreshSequence(
                (value) => value + 1
              )
            }
            disabled={
              !canQuery ||
              loadState === "loading"
            }
          >
            Refresh analytics
          </button>
        </div>
      </section>

      {showState ? (
        <section className="enterprise-analytics-state">
          <span
            className="enterprise-status-dot"
            aria-hidden="true"
          />

          <div>
            <h2>{stateTitle}</h2>
            <p>{stateDetail}</p>
          </div>
        </section>
      ) : (
        <>
          <section
            className="enterprise-dashboard-section"
            aria-labelledby="analytics-summary-title"
          >
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Summary
                </p>

                <h2 id="analytics-summary-title">
                  Recorded outcomes
                </h2>
              </div>

              <p>
                Authoritative counts for the current
                rolling 24-hour workspace window.
              </p>
            </div>

            <div className="enterprise-analytics-metric-grid">
              {summary.map((item) => (
                <article
                  className="enterprise-analytics-metric"
                  key={item.label}
                >
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
          </section>

          <section
            className="enterprise-dashboard-section"
            aria-labelledby="analytics-execution-title"
          >
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Execution
                </p>

                <h2 id="analytics-execution-title">
                  Provider and workload evidence
                </h2>
              </div>

              <p>
                Provider execution is evidence only;
                provider selection remains governed
                elsewhere.
              </p>
            </div>

            <div className="enterprise-analytics-metric-grid">
              {execution.map((item) => (
                <article
                  className="enterprise-analytics-metric"
                  key={item.label}
                >
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
          </section>

          <section
            className="enterprise-dashboard-section"
            aria-labelledby="analytics-operations-title"
          >
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Operation breakdown
                </p>

                <h2 id="analytics-operations-title">
                  Governed rewrite activity
                </h2>
              </div>

              <p>
                Each operation bucket comes directly
                from the workspace analytics contract.
              </p>
            </div>

            <div className="enterprise-analytics-operation-grid">
              {operationOrder.map(
                (operation) => {
                  const bucket =
                    operationFor(
                      snapshot,
                      operation
                    );

                  return (
                    <article
                      className="enterprise-analytics-operation"
                      key={operation}
                    >
                      <div className="enterprise-analytics-operation__header">
                        <span>
                          {OPERATION_LABELS[
                            operation
                          ]}
                        </span>

                        <strong>
                          {formatNumber(
                            bucket?.event_count ??
                              0
                          )}{" "}
                          events
                        </strong>
                      </div>

                      <dl>
                        <div>
                          <dt>Succeeded</dt>
                          <dd>
                            {formatNumber(
                              bucket
                                ?.succeeded_count ??
                                0
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt>
                            Controlled failures
                          </dt>
                          <dd>
                            {formatNumber(
                              bucket
                                ?.controlled_failure_count ??
                                0
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt>
                            System failures
                          </dt>
                          <dd>
                            {formatNumber(
                              bucket
                                ?.system_failure_count ??
                                0
                            )}
                          </dd>
                        </div>
                      </dl>
                    </article>
                  );
                }
              )}
            </div>
          </section>

          {isEmpty && (
            <section className="enterprise-analytics-empty">
              <strong>
                No recorded operations in this window
              </strong>

              <p>
                The analytics contract returned a
                valid empty workspace window. No
                operational activity is fabricated.
              </p>
            </section>
          )}

          <section className="enterprise-analytics-context">
            <div>
              <span>Workspace</span>
              <strong>
                {accessContext.context?.workspace.name ??
                  snapshot.workspace_id}
              </strong>
            </div>

            <div>
              <span>Window start</span>
              <strong>
                {formatTimestamp(
                  snapshot.period_start
                )}
              </strong>
            </div>

            <div>
              <span>Window end</span>
              <strong>
                {formatTimestamp(
                  snapshot.period_end
                )}
              </strong>
            </div>

            <div>
              <span>Generated</span>
              <strong>
                {formatTimestamp(
                  snapshot.generated_at
                )}
              </strong>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
