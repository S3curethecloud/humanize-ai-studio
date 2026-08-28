import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  WorkspaceProviderCatalogError,
  fetchWorkspaceProviderCatalog,
  type ProviderCapability,
  type WorkspaceProviderCatalogVisibility
} from "../api/providers";
import {
  type EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface ProvidersPageProps {
  accessContext: EnterpriseAccessContextState;
}

type ProviderLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "denied"
  | "error";

const PROVIDER_READ_PERMISSION =
  "provider_policy.read";

const CAPABILITY_LABELS: Record<
  ProviderCapability,
  string
> = {
  rewrite: "Rewrite",
  multi_candidate: "Multi-candidate",
  long_document: "Long document",
  claim_lock: "Claim Lock",
  voice_profile: "Voice profile"
};

export default function ProvidersPage({
  accessContext
}: ProvidersPageProps) {
  const [catalog, setCatalog] =
    useState<
      WorkspaceProviderCatalogVisibility | null
    >(null);

  const [loadState, setLoadState] =
    useState<ProviderLoadState>("idle");

  const [message, setMessage] =
    useState<string | null>(null);

  const [refreshSequence, setRefreshSequence] =
    useState(0);

  const hasReadPermission =
    accessContext.context?.permissions.includes(
      PROVIDER_READ_PERMISSION
    ) ?? false;

  const canQuery =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null &&
    hasReadPermission;

  const loadProviders = useCallback(
    async (
      signal: AbortSignal
    ) => {
      if (!canQuery) {
        setCatalog(null);
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

      setLoadState("loading");
      setMessage(
        "Loading the authorized platform provider catalog."
      );

      try {
        const nextCatalog =
          await fetchWorkspaceProviderCatalog({
            workspaceId,
            userId,
            signal
          });

        if (signal.aborted) {
          return;
        }

        setCatalog(nextCatalog);
        setLoadState("ready");
        setMessage(
          "Provider catalog loaded through the governed workspace read contract."
        );
      } catch (error: unknown) {
        if (signal.aborted) {
          return;
        }

        setCatalog(null);

        if (
          error instanceof
            WorkspaceProviderCatalogError
        ) {
          setLoadState(
            error.status === 403
              ? "denied"
              : "error"
          );
          setMessage(error.detail);
          return;
        }

        setLoadState("error");
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load provider visibility."
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

    void loadProviders(
      controller.signal
    );

    return () => {
      controller.abort();
    };
  }, [
    loadProviders,
    refreshSequence
  ]);

  const enabledCount = useMemo(
    () =>
      catalog?.targets.filter(
        (target) => target.enabled
      ).length ?? 0,
    [catalog]
  );

  let stateTitle =
    "Workspace context required";

  let stateDetail =
    "Connect a canonical workspace and user context to view provider targets.";

  if (
    accessContext.status === "loading"
  ) {
    stateTitle =
      "Resolving workspace context";
    stateDetail =
      "Provider visibility will load after canonical access context resolution.";
  } else if (
    accessContext.status === "denied"
  ) {
    stateTitle =
      "Workspace access denied";
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
      "The canonical workspace context could not be resolved.";
  } else if (
    accessContext.status === "connected" &&
    !hasReadPermission
  ) {
    stateTitle =
      "Provider visibility not granted";
    stateDetail =
      "The resolved workspace access context does not include provider_policy.read.";
  } else if (
    loadState === "loading"
  ) {
    stateTitle =
      "Loading provider catalog";
    stateDetail =
      "Requesting the platform-scoped catalog through the workspace-authorized read endpoint.";
  } else if (
    loadState === "denied"
  ) {
    stateTitle =
      "Provider access denied";
    stateDetail =
      message ??
      "The provider endpoint denied this workspace request.";
  } else if (
    loadState === "error"
  ) {
    stateTitle =
      "Provider catalog unavailable";
    stateDetail =
      message ??
      "The provider catalog could not be loaded.";
  }

  const ready =
    loadState === "ready" &&
    catalog !== null;

  return (
    <div className="enterprise-page">
      <section className="enterprise-hero">
        <div>
          <p className="enterprise-eyebrow">
            Operations
          </p>

          <h1>Provider visibility</h1>

          <p className="enterprise-hero__description">
            Read-only visibility into configured
            model-provider targets. Access is resolved
            through the canonical workspace context,
            while catalog ownership remains platform
            scoped.
          </p>
        </div>

        <div className="enterprise-hero__actions">
          <button
            type="button"
            className="enterprise-secondary-button"
            disabled={!canQuery || loadState === "loading"}
            onClick={() =>
              setRefreshSequence(
                (sequence) => sequence + 1
              )
            }
          >
            Refresh catalog
          </button>

          <span className="enterprise-release-badge">
            Platform catalog · read only
          </span>
        </div>
      </section>

      <section className="enterprise-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Governed visibility
            </p>
            <h2>Configured targets</h2>
          </div>

          <p>
            Provider configuration and credentials are
            not exposed or mutable from this surface.
          </p>
        </div>

        {!ready ? (
          <div className="enterprise-placeholder__boundary">
            <strong>{stateTitle}</strong>
            <p>{stateDetail}</p>
          </div>
        ) : catalog.targets.length === 0 ? (
          <div className="enterprise-placeholder__boundary">
            <strong>
              No provider targets available
            </strong>
            <p>
              The authorized platform catalog returned
              no visible targets.
            </p>
          </div>
        ) : (
          <>
            <p>
              <strong>
                {catalog.targets.length}
              </strong>
              {" "}targets visible ·{" "}
              <strong>{enabledCount}</strong>
              {" "}enabled · catalog scope{" "}
              <strong>{catalog.catalog_scope}</strong>
            </p>

            <div className="enterprise-table-wrap">
              <table className="enterprise-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Target</th>
                    <th>Capabilities</th>
                    <th>Status</th>
                  </tr>
                </thead>

                <tbody>
                  {catalog.targets.map(
                    (target) => (
                      <tr key={target.target_id}>
                        <td>
                          <strong>
                            {
                              target
                                .provider_display_name
                            }
                          </strong>
                          <br />
                          <small>
                            {target.provider_id}
                          </small>
                        </td>

                        <td>
                          {target.model_id}
                        </td>

                        <td>
                          <code>
                            {target.target_id}
                          </code>
                        </td>

                        <td>
                          {target.capabilities
                            .map(
                              (capability) =>
                                CAPABILITY_LABELS[
                                  capability
                                ]
                            )
                            .join(", ")}
                        </td>

                        <td>
                          <strong>
                            {target.enabled
                              ? "Enabled"
                              : "Disabled"}
                          </strong>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
