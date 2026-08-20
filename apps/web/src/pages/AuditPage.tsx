import {
  useCallback,
  useEffect,
  useState
} from "react";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  listWorkspaceHistory,
  type RewriteHistoryRecord
} from "../api/history";

interface AuditPageProps {
  accessContext: EnterpriseAccessContextState;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

export default function AuditPage({
  accessContext
}: AuditPageProps) {
  const [records, setRecords] =
    useState<RewriteHistoryRecord[]>([]);

  const [selectedId, setSelectedId] =
    useState<string | null>(null);

  const [message, setMessage] =
    useState<string | null>(null);

  const [loading, setLoading] =
    useState(false);

  const canRead =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  const load = useCallback(async () => {
    if (
      !canRead ||
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      setRecords([]);
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const next = await listWorkspaceHistory(
        accessContext.workspaceId,
        accessContext.userId,
        50
      );

      setRecords(next);

      if (
        selectedId === null &&
        next.length > 0
      ) {
        setSelectedId(next[0].rewrite_id);
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load workspace rewrite evidence."
      );
    } finally {
      setLoading(false);
    }
  }, [
    accessContext.userId,
    accessContext.workspaceId,
    canRead,
    selectedId
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  const selected =
    records.find(
      (record) =>
        record.rewrite_id === selectedId
    ) ?? null;

  if (!canRead) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Audit evidence unavailable</h1>
            <p>
              Canonical workspace access context is
              required before rewrite evidence can
              be read.
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
            Governance · Audit
          </p>

          <h1>Workspace rewrite evidence</h1>

          <p className="enterprise-hero__description">
            Review persisted rewrite history,
            provider identity, verification outcomes,
            and trace evidence for this workspace.
            This surface reflects the existing
            HISTORY_READ contract.
          </p>
        </div>

        <button
          type="button"
          className="enterprise-secondary-button"
          disabled={loading}
          onClick={() => void load()}
        >
          Refresh evidence
        </button>
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
              Rewrite history
            </p>
            <h2>Recorded executions</h2>
          </div>

          <p>{records.length} records</p>
        </div>

        {records.length === 0 ? (
          <p>
            No persisted rewrite evidence exists
            for this workspace.
          </p>
        ) : (
          <div className="enterprise-analytics-operation-grid">
            {records.map((record) => (
              <button
                type="button"
                className="enterprise-analytics-operation"
                key={record.rewrite_id}
                onClick={() =>
                  setSelectedId(record.rewrite_id)
                }
              >
                <div className="enterprise-analytics-operation__header">
                  <span>{record.trace_id}</span>
                  <strong>
                    {record.status}
                  </strong>
                </div>

                <dl>
                  <div>
                    <dt>Provider</dt>
                    <dd>{record.provider_name}</dd>
                  </div>

                  <div>
                    <dt>Model</dt>
                    <dd>{record.model_name}</dd>
                  </div>

                  <div>
                    <dt>Created</dt>
                    <dd>
                      {formatTimestamp(
                        record.created_at
                      )}
                    </dd>
                  </div>
                </dl>
              </button>
            ))}
          </div>
        )}
      </section>

      {selected && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Selected record
              </p>
              <h2>{selected.trace_id}</h2>
            </div>
          </div>

          <div className="enterprise-analytics-metric-grid">
            <article className="enterprise-analytics-metric">
              <span>Provider</span>
              <strong>
                {selected.provider_name}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Model</span>
              <strong>
                {selected.model_name}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Verification</span>
              <strong>
                {selected.verification_decision}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Editorial quality</span>
              <strong>
                {
                  selected
                    .editorial_quality_decision
                }
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Fallback used</span>
              <strong>
                {selected.fallback_used
                  ? "yes"
                  : "no"}
              </strong>
            </article>

            <article className="enterprise-analytics-metric">
              <span>Intensity</span>
              <strong>
                {selected.intensity}
              </strong>
            </article>
          </div>

          <div className="source-workspace">
            <h3>Source text</h3>
            <p>{selected.source_text}</p>

            <h3>Rewritten text</h3>
            <p>{selected.rewritten_text}</p>
          </div>
        </section>
      )}
    </div>
  );
}
