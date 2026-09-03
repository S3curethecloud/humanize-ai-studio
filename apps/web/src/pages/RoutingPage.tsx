import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  WorkspaceRoutingExecutionError,
  fetchWorkspaceRoutingExecutions,
  type RoutingOperationKind,
  type WorkspaceProviderRoutingExecutionEvidenceVisibility
} from "../api/routing";
import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface RoutingPageProps {
  accessContext: EnterpriseAccessContextState;
}

type RoutingLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "denied"
  | "error";

const ROUTING_READ_PERMISSION =
  "audit.read";

const OPERATION_KIND_LABELS: Record<
  RoutingOperationKind,
  string
> = {
  single_rewrite: "Single rewrite",
  multi_candidate_rewrite:
    "Multi-candidate rewrite",
  long_document_rewrite:
    "Long-document rewrite"
};

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

export default function RoutingPage({
  accessContext
}: RoutingPageProps) {
  const [records, setRecords] =
    useState<
      WorkspaceProviderRoutingExecutionEvidenceVisibility[]
    >([]);

  const [selectedId, setSelectedId] =
    useState<string | null>(
      null
    );

  const [loadState, setLoadState] =
    useState<RoutingLoadState>(
      "idle"
    );

  const [message, setMessage] =
    useState<string | null>(
      null
    );

  const [refreshSequence, setRefreshSequence] =
    useState(
      0
    );

  const hasReadPermission =
    accessContext.context?.permissions.includes(
      ROUTING_READ_PERMISSION
    ) ?? false;

  const canQuery =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null &&
    hasReadPermission;

  const loadRouting = useCallback(
    async (
      signal: AbortSignal
    ) => {
      if (!canQuery) {
        setRecords([]);
        setSelectedId(null);
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
        "Loading authorized routing execution evidence."
      );

      try {
        const next =
          await fetchWorkspaceRoutingExecutions({
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

        setSelectedId(
          (current) => {
            if (
              current !== null &&
              next.records.some(
                (record) =>
                  record.operation.operation_id ===
                  current
              )
            ) {
              return current;
            }

            return (
              next.records[0]
                ?.operation
                .operation_id ??
              null
            );
          }
        );

        setLoadState(
          "ready"
        );

        setMessage(
          "Routing execution evidence loaded through the workspace-authorized read contract."
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
        setSelectedId(null);

        if (
          error instanceof
            WorkspaceRoutingExecutionError
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
            : "Unable to load routing execution evidence."
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

      void loadRouting(
        controller.signal
      );

      return () => {
        controller.abort();
      };
    },
    [
      loadRouting,
      refreshSequence
    ]
  );

  const selected =
    useMemo(
      () =>
        records.find(
          (record) =>
            record.operation.operation_id ===
            selectedId
        ) ?? null,
      [
        records,
        selectedId
      ]
    );

  let stateTitle =
    "Workspace context required";

  let stateDetail =
    "Connect a canonical workspace and user context to view routing execution evidence.";

  if (
    accessContext.status ===
    "loading"
  ) {
    stateTitle =
      "Resolving workspace context";

    stateDetail =
      "Routing evidence will load after canonical access context resolution.";
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
      "Routing evidence not granted";

    stateDetail =
      "The resolved workspace access context does not include audit.read.";
  } else if (
    loadState ===
    "loading"
  ) {
    stateTitle =
      "Loading routing evidence";

    stateDetail =
      "Requesting workspace-authorized routing operations and linked execution evidence.";
  } else if (
    loadState ===
    "denied"
  ) {
    stateTitle =
      "Routing evidence access denied";

    stateDetail =
      message ??
      "The routing evidence endpoint denied this workspace request.";
  } else if (
    loadState ===
    "error"
  ) {
    stateTitle =
      "Routing evidence unavailable";

    stateDetail =
      message ??
      "Routing execution evidence could not be loaded.";
  }

  const ready =
    loadState ===
    "ready";

  return (
    <div className="enterprise-page">
      <section className="enterprise-hero">
        <div>
          <p className="enterprise-eyebrow">
            Operations
          </p>

          <h1>
            Routing execution evidence
          </h1>

          <p className="enterprise-hero__description">
            Read-only visibility into governed
            provider-routing operations and their
            linked execution evidence. Workspace
            authorization remains server controlled;
            this interface only presents persisted
            evidence.
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
            Workspace evidence · read only
          </span>
        </div>
      </section>

      <section className="enterprise-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Governed execution
            </p>

            <h2>
              Recorded routing operations
            </h2>
          </div>

          <p>
            Policy administration and routing
            execution controls are intentionally
            unavailable from this surface.
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
              No routing execution evidence
            </strong>

            <p>
              No enterprise routing operations are
              currently recorded for this workspace.
            </p>
          </div>
        ) : (
          <>
            <p>
              <strong>
                {records.length}
              </strong>
              {" "}
              routing operations visible through the
              authorized workspace evidence contract.
            </p>

            <div className="enterprise-analytics-operation-grid">
              {records.map(
                (record) => {
                  const operation =
                    record.operation;

                  return (
                    <button
                      type="button"
                      className="enterprise-analytics-operation"
                      key={
                        operation.operation_id
                      }
                      aria-pressed={
                        selectedId ===
                        operation.operation_id
                      }
                      onClick={() =>
                        setSelectedId(
                          operation.operation_id
                        )
                      }
                    >
                      <div className="enterprise-analytics-operation__header">
                        <span>
                          {
                            operation
                              .operation_id
                          }
                        </span>

                        <strong>
                          {displayStatus(
                            operation.status
                          )}
                        </strong>
                      </div>

                      <dl>
                        <div>
                          <dt>
                            Operation
                          </dt>
                          <dd>
                            {
                              OPERATION_KIND_LABELS[
                                operation
                                  .operation_kind
                              ]
                            }
                          </dd>
                        </div>

                        <div>
                          <dt>
                            Policy
                          </dt>
                          <dd>
                            {
                              operation
                                .policy_id
                            }
                          </dd>
                        </div>

                        <div>
                          <dt>
                            Created
                          </dt>
                          <dd>
                            {formatTimestamp(
                              operation
                                .created_at
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt>
                            Bindings
                          </dt>
                          <dd>
                            {
                              record
                                .bindings
                                .length
                            }
                          </dd>
                        </div>
                      </dl>
                    </button>
                  );
                }
              )}
            </div>
          </>
        )}
      </section>

      {selected && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Selected operation
              </p>

              <h2>
                {
                  selected
                    .operation
                    .operation_id
                }
              </h2>
            </div>

            <p>
              Local selection only · authoritative
              values remain server supplied.
            </p>
          </div>

          <div className="enterprise-analytics-metric-grid">
            <article className="enterprise-analytics-metric">
              <span>
                Operation
              </span>

              <strong>
                {
                  OPERATION_KIND_LABELS[
                    selected
                      .operation
                      .operation_kind
                  ]
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Status
              </span>

              <strong>
                {displayStatus(
                  selected
                    .operation
                    .status
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Policy
              </span>

              <strong>
                {
                  selected
                    .operation
                    .policy_id
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Policy revision
              </span>

              <strong>
                {
                  selected
                    .operation
                    .policy_revision
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Required capabilities
              </span>

              <strong>
                {
                  selected
                    .operation
                    .required_capabilities
                    .join(", ") ||
                  "None"
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Revision
              </span>

              <strong>
                {
                  selected
                    .operation
                    .revision
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Rewrite history
              </span>

              <strong>
                {
                  selected
                    .operation
                    .rewrite_history_id ??
                  "None"
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Long-document audit
              </span>

              <strong>
                {
                  selected
                    .operation
                    .long_document_audit_id ??
                  "None"
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Failure code
              </span>

              <strong>
                {
                  selected
                    .operation
                    .failure_code ??
                  "None"
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Created
              </span>

              <strong>
                {formatTimestamp(
                  selected
                    .operation
                    .created_at
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Updated
              </span>

              <strong>
                {formatTimestamp(
                  selected
                    .operation
                    .updated_at
                )}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>
                Evidence bindings
              </span>

              <strong>
                {
                  selected
                    .bindings
                    .length
                }
              </strong>
            </article>
          </div>

          <section className="enterprise-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Routing evidence
                </p>

                <h2>
                  Provider execution bindings
                </h2>
              </div>

              <p>
                Reserved bindings remain explicitly
                unresolved. Recorded bindings include
                only the linked platform evidence
                returned by the workspace endpoint.
              </p>
            </div>

            {
              selected
                .bindings
                .length === 0
                ? (
                  <div className="enterprise-placeholder__boundary">
                    <strong>
                      {
                        selected
                          .operation
                          .status ===
                        "no_provider_execution"
                          ? "No provider execution required"
                          : "No routing evidence bindings"
                      }
                    </strong>

                    <p>
                      {
                        selected
                          .operation
                          .status ===
                        "no_provider_execution"
                          ? "The enterprise routing operation is authoritative and correctly records zero provider-routing evidence bindings."
                          : "This operation currently contains no provider-routing evidence bindings."
                      }
                    </p>
                  </div>
                )
                : (
                  <div className="enterprise-table-wrap">
                    <table className="enterprise-table">
                      <thead>
                        <tr>
                          <th>
                            Ordinal
                          </th>
                          <th>
                            Evidence
                          </th>
                          <th>
                            Binding
                          </th>
                          <th>
                            Outcome
                          </th>
                          <th>
                            Executed target
                          </th>
                          <th>
                            Fallback
                          </th>
                          <th>
                            Observed
                          </th>
                        </tr>
                      </thead>

                      <tbody>
                        {
                          selected
                            .bindings
                            .map(
                              (bindingView) => {
                                const evidence =
                                  bindingView
                                    .routing_evidence;

                                return (
                                  <tr
                                    key={
                                      bindingView
                                        .binding
                                        .evidence_id
                                    }
                                  >
                                    <td>
                                      {
                                        bindingView
                                          .binding
                                          .ordinal
                                      }
                                    </td>

                                    <td>
                                      <code>
                                        {
                                          bindingView
                                            .binding
                                            .evidence_id
                                        }
                                      </code>
                                    </td>

                                    <td>
                                      <strong>
                                        {displayStatus(
                                          bindingView
                                            .binding
                                            .status
                                        )}
                                      </strong>
                                    </td>

                                    <td>
                                      {
                                        evidence
                                          ? displayStatus(
                                              evidence
                                                .execution_outcome
                                            )
                                          : "Unresolved"
                                      }
                                    </td>

                                    <td>
                                      {
                                        evidence
                                          ?.executed_target_id ??
                                        "—"
                                      }
                                    </td>

                                    <td>
                                      {
                                        evidence
                                          ? (
                                              evidence
                                                .execution_fallback_used
                                                ? "yes"
                                                : "no"
                                            )
                                          : "—"
                                      }
                                    </td>

                                    <td>
                                      {
                                        evidence
                                          ? formatTimestamp(
                                              evidence
                                                .observed_at
                                            )
                                          : "—"
                                      }
                                    </td>
                                  </tr>
                                );
                              }
                            )
                        }
                      </tbody>
                    </table>
                  </div>
                )
            }
          </section>
        </section>
      )}
    </div>
  );
}
