import {
  useCallback,
  useEffect,
  useState
} from "react";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  archiveEnterpriseClaimLockPolicy,
  createEnterpriseClaimLockPolicy,
  disableEnterpriseClaimLockPolicy,
  enableEnterpriseClaimLockPolicy,
  EnterpriseClaimLockApiError,
  getEnterpriseClaimLockPolicy,
  updateEnterpriseClaimLockPolicy,
  type ClaimLockEnforcementMode,
  type EnterpriseClaimLockPolicyTermInput,
  type EnterpriseWorkspaceClaimLockPolicy
} from "../api/claimLock";

interface ClaimLockPageProps {
  accessContext: EnterpriseAccessContextState;
}

type LifecycleAction =
  | "enable"
  | "disable"
  | "archive";

function emptyTerm():
EnterpriseClaimLockPolicyTermInput {
  return {
    term_id: "",
    text: "",
    case_sensitive: true
  };
}

function editableTerms(
  policy: EnterpriseWorkspaceClaimLockPolicy
): EnterpriseClaimLockPolicyTermInput[] {
  return policy.protected_terms.map(
    (term) => ({
      term_id: term.term_id,
      text: term.text,
      case_sensitive: term.case_sensitive
    })
  );
}

function displayMode(
  mode: ClaimLockEnforcementMode
): string {
  return mode === "strict"
    ? "Strict"
    : "Audit only";
}

function displayStatus(
  status:
    EnterpriseWorkspaceClaimLockPolicy["status"]
): string {
  return (
    status.charAt(0).toUpperCase() +
    status.slice(1)
  );
}

function displayReason(
  value: string
): string {
  return value
    .split("_")
    .filter(Boolean)
    .map(
      (part) =>
        part.charAt(0).toUpperCase() +
        part.slice(1)
    )
    .join(" ");
}

function policyErrorMessage(
  error: unknown,
  operation: string
): string {
  if (
    error instanceof EnterpriseClaimLockApiError
  ) {
    if (error.status === 403) {
      return (
        "Claim Lock policy access was denied " +
        "by server authorization."
      );
    }

    if (error.status === 404) {
      return "No Claim Lock policy was found.";
    }

    if (error.status === 422) {
      return (
        "The server rejected the Claim Lock " +
        "policy input as invalid."
      );
    }

    if (error.status >= 500) {
      return (
        "Claim Lock governance is currently " +
        "unavailable because the server could " +
        "not complete the operation."
      );
    }

    return (
      `${operation} failed: ` +
      `${displayReason(error.detail)}.`
    );
  }

  return error instanceof Error
    ? error.message
    : `${operation} failed.`;
}

function formatDate(
  value: string
): string {
  return new Date(value).toLocaleString();
}

export default function ClaimLockPage({
  accessContext
}: ClaimLockPageProps) {
  const [policy, setPolicy] =
    useState<
      EnterpriseWorkspaceClaimLockPolicy | null
    >(null);

  const [policyId, setPolicyId] =
    useState("");

  const [enforcementMode, setEnforcementMode] =
    useState<ClaimLockEnforcementMode>(
      "strict"
    );

  const [terms, setTerms] =
    useState<
      EnterpriseClaimLockPolicyTermInput[]
    >([]);

  const [message, setMessage] =
    useState<string | null>(null);

  const [busy, setBusy] =
    useState(false);

  const canUse =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  const permissions =
    accessContext.context?.permissions ?? [];

  const canRead =
    permissions.includes("claim_lock.read");

  const canManage =
    permissions.includes("claim_lock.manage");

  const applyPolicy = useCallback(
    (
      next:
        EnterpriseWorkspaceClaimLockPolicy
    ) => {
      setPolicy(next);
      setPolicyId(next.policy_id);
      setEnforcementMode(
        next.enforcement_mode
      );
      setTerms(editableTerms(next));
    },
    []
  );

  const resetCreateDraft = useCallback(
    () => {
      setPolicy(null);
      setPolicyId("");
      setEnforcementMode("strict");
      setTerms([]);
    },
    []
  );

  const load = useCallback(
    async (): Promise<boolean> => {
      if (
        !canUse ||
        !canRead ||
        accessContext.workspaceId === null ||
        accessContext.userId === null
      ) {
        setPolicy(null);
        return false;
      }

      setBusy(true);

      try {
        const next =
          await getEnterpriseClaimLockPolicy(
            accessContext.workspaceId,
            accessContext.userId
          );

        applyPolicy(next);
        setMessage(null);
        return true;
      } catch (error) {
        if (
          error instanceof
            EnterpriseClaimLockApiError &&
          error.status === 404
        ) {
          resetCreateDraft();
          setMessage(null);
          return true;
        }

        setPolicy(null);
        setMessage(
          policyErrorMessage(
            error,
            "Loading Claim Lock policy"
          )
        );
        return false;
      } finally {
        setBusy(false);
      }
    },
    [
      accessContext.userId,
      accessContext.workspaceId,
      applyPolicy,
      canRead,
      canUse,
      resetCreateDraft
    ]
  );

  useEffect(() => {
    void load();
  }, [load]);

  function normalizedTerms():
  EnterpriseClaimLockPolicyTermInput[] | null {
    const normalized:
      EnterpriseClaimLockPolicyTermInput[] = [];

    for (const term of terms) {
      const termId =
        term.term_id.trim();
      const text =
        term.text.trim();

      if (
        termId === "" &&
        text === ""
      ) {
        continue;
      }

      if (
        termId === "" ||
        text === ""
      ) {
        setMessage(
          "Every protected term must have " +
          "both a term ID and protected text."
        );
        return null;
      }

      normalized.push({
        term_id: termId,
        text,
        case_sensitive:
          term.case_sensitive
      });
    }

    return normalized;
  }

  async function handleMutationError(
    error: unknown,
    operation: string
  ) {
    if (
      error instanceof
        EnterpriseClaimLockApiError &&
      error.status === 409
    ) {
      const reason = error.detail;
      const refreshed = await load();

      if (reason === "revision_conflict") {
        setMessage(
          refreshed
            ? (
                "The policy changed on the " +
                "server. Canonical state was " +
                "refreshed; review the new " +
                "revision before retrying."
              )
            : (
                "The policy changed on the " +
                "server, and canonical refresh " +
                "did not complete. Refresh " +
                "before attempting another " +
                "mutation."
              )
        );
        return;
      }

      setMessage(
        refreshed
          ? (
              `${operation} was rejected by ` +
              `the server: ` +
              `${displayReason(reason)}. ` +
              "Canonical policy state was " +
              "refreshed."
            )
          : (
              `${operation} was rejected by ` +
              `the server: ` +
              `${displayReason(reason)}. ` +
              "Refresh canonical policy state " +
              "before attempting another " +
              "mutation."
            )
      );
      return;
    }

    setMessage(
      policyErrorMessage(
        error,
        operation
      )
    );
  }

  async function handleCreate() {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null ||
      !canManage
    ) {
      return;
    }

    const nextPolicyId =
      policyId.trim();

    if (nextPolicyId === "") {
      setMessage(
        "Policy ID is required."
      );
      return;
    }

    const nextTerms =
      normalizedTerms();

    if (nextTerms === null) {
      return;
    }

    setBusy(true);
    setMessage(
      "Creating governed Claim Lock policy."
    );

    try {
      const next =
        await createEnterpriseClaimLockPolicy(
          accessContext.workspaceId,
          {
            actor_user_id:
              accessContext.userId,
            policy_id: nextPolicyId,
            enforcement_mode:
              enforcementMode,
            protected_terms: nextTerms
          }
        );

      applyPolicy(next);
      setMessage(
        "Workspace Claim Lock policy created."
      );
    } catch (error) {
      await handleMutationError(
        error,
        "Creating Claim Lock policy"
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUpdate() {
    if (
      policy === null ||
      policy.status === "archived" ||
      accessContext.workspaceId === null ||
      accessContext.userId === null ||
      !canManage
    ) {
      return;
    }

    const nextTerms =
      normalizedTerms();

    if (nextTerms === null) {
      return;
    }

    setBusy(true);
    setMessage(
      "Updating governed Claim Lock policy."
    );

    try {
      const next =
        await updateEnterpriseClaimLockPolicy(
          accessContext.workspaceId,
          {
            actor_user_id:
              accessContext.userId,
            policy_id:
              policy.policy_id,
            expected_revision:
              policy.revision,
            enforcement_mode:
              enforcementMode,
            protected_terms: nextTerms
          }
        );

      applyPolicy(next);
      setMessage(
        "Workspace Claim Lock policy updated."
      );
    } catch (error) {
      await handleMutationError(
        error,
        "Updating Claim Lock policy"
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleLifecycle(
    action: LifecycleAction
  ) {
    if (
      policy === null ||
      policy.status === "archived" ||
      accessContext.workspaceId === null ||
      accessContext.userId === null ||
      !canManage
    ) {
      return;
    }

    if (
      action === "archive" &&
      !window.confirm(
        "Archive this Claim Lock policy? " +
        "Archived is terminal in the current " +
        "policy lifecycle."
      )
    ) {
      return;
    }

    setBusy(true);
    setMessage(
      `${displayReason(action)} Claim Lock policy.`
    );

    const input = {
      actor_user_id:
        accessContext.userId,
      policy_id:
        policy.policy_id,
      expected_revision:
        policy.revision
    };

    try {
      let next:
        EnterpriseWorkspaceClaimLockPolicy;

      if (action === "enable") {
        next =
          await enableEnterpriseClaimLockPolicy(
            accessContext.workspaceId,
            input
          );
      } else if (action === "disable") {
        next =
          await disableEnterpriseClaimLockPolicy(
            accessContext.workspaceId,
            input
          );
      } else {
        next =
          await archiveEnterpriseClaimLockPolicy(
            accessContext.workspaceId,
            input
          );
      }

      applyPolicy(next);
      setMessage(
        action === "archive"
          ? "Claim Lock policy archived."
          : (
              `Claim Lock policy ` +
              `${action}d.`
            )
      );
    } catch (error) {
      await handleMutationError(
        error,
        `${displayReason(action)} Claim Lock policy`
      );
    } finally {
      setBusy(false);
    }
  }

  function updateTerm(
    index: number,
    next:
      EnterpriseClaimLockPolicyTermInput
  ) {
    setTerms(
      (current) =>
        current.map(
          (term, termIndex) =>
            termIndex === index
              ? next
              : term
        )
    );
  }

  function removeTerm(
    index: number
  ) {
    setTerms(
      (current) =>
        current.filter(
          (_, termIndex) =>
            termIndex !== index
        )
    );
  }

  if (!canUse) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Claim Lock unavailable</h1>
            <p>
              Canonical workspace access context is
              required before Claim Lock governance
              can be presented.
            </p>
          </div>
        </section>
      </div>
    );
  }

  if (!canRead) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Claim Lock unavailable</h1>
            <p>
              Canonical workspace permissions do
              not grant claim_lock.read for this
              workspace.
            </p>
          </div>
        </section>
      </div>
    );
  }

  const isArchived =
    policy?.status === "archived";

  return (
    <div className="enterprise-page enterprise-claim-lock">
      <section className="enterprise-analytics-hero">
        <div>
          <p className="enterprise-eyebrow">
            Governance · Claim Lock
          </p>

          <h1>Workspace Claim Lock</h1>

          <p className="enterprise-hero__description">
            Inspect and administer the canonical
            workspace policy for protected facts
            and terminology. Server authorization,
            lifecycle state, and policy revision
            remain authoritative.
          </p>
        </div>

        <div className="enterprise-analytics-hero__actions">
          <button
            type="button"
            className="enterprise-secondary-button"
            disabled={busy}
            onClick={() => void load()}
          >
            Refresh policy
          </button>
        </div>
      </section>

      {message && (
        <section className="enterprise-analytics-state">
          <div>
            <p>{message}</p>
          </div>
        </section>
      )}

      {policy === null ? (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Current policy
              </p>
              <h2>No policy configured</h2>
            </div>

            <p>
              The server returned no canonical
              Claim Lock policy for this workspace.
            </p>
          </div>
        </section>
      ) : (
        <>
          <section className="enterprise-dashboard-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Canonical policy
                </p>
                <h2>{policy.policy_id}</h2>
              </div>

              <span
                className={
                  "enterprise-claim-lock-status " +
                  `enterprise-claim-lock-status--${policy.status}`
                }
              >
                {displayStatus(policy.status)}
              </span>
            </div>

            <div className="enterprise-analytics-context">
              <div>
                <span>Enforcement</span>
                <strong>
                  {displayMode(
                    policy.enforcement_mode
                  )}
                </strong>
              </div>

              <div>
                <span>Revision</span>
                <strong>
                  {policy.revision}
                </strong>
              </div>

              <div>
                <span>Protected terms</span>
                <strong>
                  {policy.protected_terms.length}
                </strong>
              </div>

              <div>
                <span>Updated</span>
                <strong>
                  {formatDate(
                    policy.updated_at
                  )}
                </strong>
              </div>
            </div>
          </section>

          <section className="enterprise-dashboard-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Protected terminology
                </p>
                <h2>Current protected terms</h2>
              </div>
            </div>

            {policy.protected_terms.length === 0 ? (
              <p className="enterprise-claim-lock-muted">
                No workspace protected terms are
                configured.
              </p>
            ) : (
              <div className="enterprise-analytics-operation-grid">
                {policy.protected_terms.map(
                  (term) => (
                    <article
                      className="enterprise-analytics-operation"
                      key={term.term_id}
                    >
                      <div className="enterprise-analytics-operation__header">
                        <span>
                          {term.term_id}
                        </span>
                        <strong>
                          {term.text}
                        </strong>
                      </div>

                      <dl>
                        <div>
                          <dt>Case sensitive</dt>
                          <dd>
                            {term.case_sensitive
                              ? "Yes"
                              : "No"}
                          </dd>
                        </div>
                      </dl>
                    </article>
                  )
                )}
              </div>
            )}
          </section>
        </>
      )}

      {canManage && !isArchived && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Administration
              </p>
              <h2>
                {policy === null
                  ? "Create policy"
                  : "Edit current policy"}
              </h2>
            </div>

            <p>
              Client controls initiate requests
              only. Server authorization and
              revision checks remain final.
            </p>
          </div>

          <div className="enterprise-claim-lock-form">
            <div className="enterprise-claim-lock-field-grid">
              <label>
                Policy ID
                <input
                  type="text"
                  maxLength={200}
                  value={policyId}
                  disabled={
                    busy ||
                    policy !== null
                  }
                  onChange={(event) =>
                    setPolicyId(
                      event.target.value
                    )
                  }
                />
              </label>

              <label>
                Enforcement mode
                <select
                  value={enforcementMode}
                  disabled={busy}
                  onChange={(event) =>
                    setEnforcementMode(
                      event.target.value as
                        ClaimLockEnforcementMode
                    )
                  }
                >
                  <option value="strict">
                    Strict
                  </option>
                  <option value="audit_only">
                    Audit only
                  </option>
                </select>
              </label>
            </div>

            <div className="enterprise-claim-lock-term-editor">
              <div className="enterprise-claim-lock-term-editor__header">
                <div>
                  <strong>Protected terms</strong>
                  <p>
                    Zero or more workspace terms
                    may be configured.
                  </p>
                </div>

                <button
                  type="button"
                  className="enterprise-secondary-button"
                  disabled={busy}
                  onClick={() =>
                    setTerms(
                      (current) => [
                        ...current,
                        emptyTerm()
                      ]
                    )
                  }
                >
                  Add term
                </button>
              </div>

              {terms.length === 0 ? (
                <p className="enterprise-claim-lock-muted">
                  No protected terms in this
                  policy draft.
                </p>
              ) : (
                <div className="enterprise-claim-lock-term-list">
                  {terms.map(
                    (term, index) => (
                      <div
                        className="enterprise-claim-lock-term-row"
                        key={index}
                      >
                        <label>
                          Term ID
                          <input
                            type="text"
                            maxLength={200}
                            value={
                              term.term_id
                            }
                            disabled={busy}
                            onChange={(event) =>
                              updateTerm(
                                index,
                                {
                                  ...term,
                                  term_id:
                                    event
                                      .target
                                      .value
                                }
                              )
                            }
                          />
                        </label>

                        <label>
                          Protected text
                          <input
                            type="text"
                            maxLength={1000}
                            value={term.text}
                            disabled={busy}
                            onChange={(event) =>
                              updateTerm(
                                index,
                                {
                                  ...term,
                                  text:
                                    event
                                      .target
                                      .value
                                }
                              )
                            }
                          />
                        </label>

                        <label className="enterprise-claim-lock-checkbox">
                          <input
                            type="checkbox"
                            checked={
                              term.case_sensitive
                            }
                            disabled={busy}
                            onChange={(event) =>
                              updateTerm(
                                index,
                                {
                                  ...term,
                                  case_sensitive:
                                    event
                                      .target
                                      .checked
                                }
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
                            removeTerm(index)
                          }
                        >
                          Remove
                        </button>
                      </div>
                    )
                  )}
                </div>
              )}
            </div>

            <div className="enterprise-claim-lock-actions">
              <button
                type="button"
                className="enterprise-primary-button"
                disabled={busy}
                onClick={() =>
                  policy === null
                    ? void handleCreate()
                    : void handleUpdate()
                }
              >
                {policy === null
                  ? "Create policy"
                  : "Save policy revision"}
              </button>
            </div>
          </div>
        </section>
      )}

      {canManage &&
        policy !== null &&
        !isArchived && (
          <section className="enterprise-dashboard-section">
            <div className="enterprise-section__heading">
              <div>
                <p className="enterprise-eyebrow">
                  Lifecycle
                </p>
                <h2>Policy state</h2>
              </div>

              <p>
                Every lifecycle mutation uses the
                currently loaded server revision.
              </p>
            </div>

            <div className="enterprise-claim-lock-actions">
              {policy.status === "active" && (
                <button
                  type="button"
                  className="enterprise-secondary-button"
                  disabled={busy}
                  onClick={() =>
                    void handleLifecycle(
                      "disable"
                    )
                  }
                >
                  Disable policy
                </button>
              )}

              {policy.status === "disabled" && (
                <button
                  type="button"
                  className="enterprise-secondary-button"
                  disabled={busy}
                  onClick={() =>
                    void handleLifecycle(
                      "enable"
                    )
                  }
                >
                  Enable policy
                </button>
              )}

              <button
                type="button"
                className="enterprise-secondary-button enterprise-claim-lock-button--danger"
                disabled={busy}
                onClick={() =>
                  void handleLifecycle(
                    "archive"
                  )
                }
              >
                Archive policy
              </button>
            </div>
          </section>
        )}

      {policy !== null && isArchived && (
        <section className="enterprise-analytics-state">
          <div>
            <h2>Archived policy</h2>
            <p>
              Archived is terminal in the current
              Claim Lock policy lifecycle. No
              update, enable, disable, archive, or
              restoration control is presented.
            </p>
          </div>
        </section>
      )}

      {policy !== null && (
        <section className="enterprise-dashboard-section">
          <div className="enterprise-section__heading">
            <div>
              <p className="enterprise-eyebrow">
                Policy evidence
              </p>
              <h2>Server metadata</h2>
            </div>
          </div>

          <div className="enterprise-analytics-context">
            <div>
              <span>Policy version</span>
              <strong>
                {policy.policy_version}
              </strong>
            </div>

            <div>
              <span>Created by</span>
              <strong>
                {policy.created_by_user_id}
              </strong>
            </div>

            <div>
              <span>Created</span>
              <strong>
                {formatDate(
                  policy.created_at
                )}
              </strong>
            </div>

            <div>
              <span>Updated by</span>
              <strong>
                {policy.updated_by_user_id}
              </strong>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
