import {
  useCallback,
  useEffect,
  useState
} from "react";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  createQuotaLimit,
  listQuotaLimits,
  type EnterpriseQuotaDimension,
  type EnterpriseQuotaLimit
} from "../api/quotas";

interface QuotasPageProps {
  accessContext: EnterpriseAccessContextState;
}

const DIMENSIONS: EnterpriseQuotaDimension[] = [
  "rewrite_requests",
  "input_characters",
  "output_characters",
  "candidates_generated",
  "long_document_sections"
];

function defaultWindowStart(): string {
  return new Date().toISOString();
}

function defaultWindowEnd(): string {
  const end = new Date();
  end.setDate(end.getDate() + 30);
  return end.toISOString();
}

function generateLimitId(
  dimension: EnterpriseQuotaDimension
): string {
  return `quota_${dimension}_${Date.now()}`;
}

export default function QuotasPage({
  accessContext
}: QuotasPageProps) {
  const [dimension, setDimension] =
    useState<EnterpriseQuotaDimension>(
      "rewrite_requests"
    );

  const [limits, setLimits] =
    useState<EnterpriseQuotaLimit[]>([]);

  const [limitValue, setLimitValue] =
    useState("100");

  const [message, setMessage] =
    useState<string | null>(null);

  const [busy, setBusy] =
    useState(false);

  const canUse =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  const load = useCallback(async () => {
    if (
      !canUse ||
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      setLimits([]);
      return;
    }

    setBusy(true);

    try {
      const next = await listQuotaLimits(
        accessContext.workspaceId,
        accessContext.userId,
        dimension
      );

      setLimits(next);
      setMessage(null);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load quota limits."
      );
    } finally {
      setBusy(false);
    }
  }, [
    accessContext.userId,
    accessContext.workspaceId,
    canUse,
    dimension
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate() {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    const parsedLimit = Number(limitValue);

    if (
      !Number.isInteger(parsedLimit) ||
      parsedLimit < 0
    ) {
      setMessage(
        "Quota limit must be a non-negative integer."
      );
      return;
    }

    setBusy(true);
    setMessage(
      "Creating governed workspace quota limit."
    );

    try {
      await createQuotaLimit(
        accessContext.workspaceId,
        accessContext.userId,
        {
          quotaLimitId:
            generateLimitId(dimension),
          dimension,
          windowStart:
            defaultWindowStart(),
          windowEnd:
            defaultWindowEnd(),
          limit: parsedLimit
        }
      );

      await load();

      setMessage(
        "Workspace quota limit created."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to create quota limit."
      );
    } finally {
      setBusy(false);
    }
  }

  if (!canUse) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Quotas unavailable</h1>
            <p>
              Canonical workspace access context is
              required before quota administration.
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
            Admin · Quotas
          </p>

          <h1>Workspace quotas</h1>

          <p className="enterprise-hero__description">
            Inspect and administer governed
            workspace quota limits using the
            enterprise quota authority.
          </p>
        </div>

        <button
          type="button"
          className="enterprise-secondary-button"
          disabled={busy}
          onClick={() => void load()}
        >
          Refresh quotas
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
              Quota dimension
            </p>
            <h2>Configured limits</h2>
          </div>
        </div>

        <div className="source-workspace">
          <label>
            Dimension
            <select
              value={dimension}
              disabled={busy}
              onChange={(event) =>
                setDimension(
                  event.target.value as
                    EnterpriseQuotaDimension
                )
              }
            >
              {DIMENSIONS.map((value) => (
                <option
                  key={value}
                  value={value}
                >
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>

        {limits.length === 0 ? (
          <p>
            No quota limits are configured for this
            dimension.
          </p>
        ) : (
          <div className="enterprise-analytics-operation-grid">
            {limits.map((quota) => (
              <article
                className="enterprise-analytics-operation"
                key={quota.quota_limit_id}
              >
                <div className="enterprise-analytics-operation__header">
                  <span>
                    {quota.quota_limit_id}
                  </span>
                  <strong>
                    {quota.limit}
                  </strong>
                </div>

                <dl>
                  <div>
                    <dt>Dimension</dt>
                    <dd>
                      {quota.dimension}
                    </dd>
                  </div>

                  <div>
                    <dt>Window start</dt>
                    <dd>
                      {new Date(
                        quota.window.window_start
                      ).toLocaleString()}
                    </dd>
                  </div>

                  <div>
                    <dt>Window end</dt>
                    <dd>
                      {new Date(
                        quota.window.window_end
                      ).toLocaleString()}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Administration
            </p>
            <h2>Create quota limit</h2>
          </div>
        </div>

        <div className="source-workspace">
          <label>
            Limit
            <input
              type="number"
              min="0"
              step="1"
              value={limitValue}
              disabled={busy}
              onChange={(event) =>
                setLimitValue(
                  event.target.value
                )
              }
            />
          </label>

          <p>
            A new 30-day timezone-aware quota
            window will begin when this limit is
            created.
          </p>

          <button
            type="button"
            className="enterprise-secondary-button"
            disabled={busy}
            onClick={() =>
              void handleCreate()
            }
          >
            Create quota limit
          </button>
        </div>
      </section>
    </div>
  );
}
