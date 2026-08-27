import type {
  ClaimLockEnforcementMode,
  ClaimLockRewriteEvidence,
  ClaimLockValidationCheck
} from "../api/claimLock";

interface ClaimLockExecutionEvidenceProps {
  evidence:
    ClaimLockRewriteEvidence |
    null |
    undefined;
}

function displayMode(
  mode: ClaimLockEnforcementMode
): string {
  return mode === "strict"
    ? "Strict"
    : "Audit only";
}

function displayDecision(
  value: string
): string {
  return (
    value.charAt(0).toUpperCase() +
    value.slice(1).replaceAll("_", " ")
  );
}

function checkTone(
  check: ClaimLockValidationCheck
): string {
  return (
    "enterprise-claim-lock-execution-check " +
    `enterprise-claim-lock-execution-check--${check.status}`
  );
}

export default function ClaimLockExecutionEvidence({
  evidence
}: ClaimLockExecutionEvidenceProps) {
  if (evidence == null) {
    return (
      <section className="enterprise-dashboard-section enterprise-claim-lock-execution">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Claim Lock execution
            </p>
            <h2>Current execution evidence</h2>
          </div>
        </div>

        <div className="enterprise-analytics-state">
          <div>
            <h2>No Claim Lock evidence returned</h2>
            <p>
              This server response did not include
              Claim Lock execution evidence. The
              browser does not infer policy state,
              effective mode, or protected items.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const preparation = evidence.preparation;
  const validation = evidence.validation;
  const effectiveLock =
    preparation.claim_lock ?? null;
  const workspacePolicy =
    evidence.workspace_policy ?? null;

  return (
    <section className="enterprise-dashboard-section enterprise-claim-lock-execution">
      <div className="enterprise-section__heading">
        <div>
          <p className="enterprise-eyebrow">
            Claim Lock execution
          </p>
          <h2>Current execution evidence</h2>
        </div>

        <p>
          Server-produced preparation, validation,
          and workspace-policy execution evidence.
        </p>
      </div>

      <div className="enterprise-analytics-context">
        <div>
          <span>Effective lock</span>
          <strong>
            {effectiveLock === null
              ? "Not materialized"
              : effectiveLock.lock_id}
          </strong>
        </div>

        <div>
          <span>Validation</span>
          <strong>
            {displayDecision(
              validation.decision
            )}
          </strong>
        </div>

        <div>
          <span>Validation mode</span>
          <strong>
            {validation.enforcement_mode == null
              ? "Not returned"
              : displayMode(
                  validation.enforcement_mode
                )}
          </strong>
        </div>

        <div>
          <span>Validation checks</span>
          <strong>
            {validation.checks.length}
          </strong>
        </div>
      </div>

      <div className="enterprise-claim-lock-execution-grid">
        <article className="enterprise-analytics-operation">
          <div className="enterprise-analytics-operation__header">
            <span>Preparation</span>
            <strong>
              Server extraction evidence
            </strong>
          </div>

          <dl>
            <div>
              <dt>Claims selected</dt>
              <dd>
                {
                  preparation
                    .claim_extraction
                    .claims.length
                }
              </dd>
            </div>

            <div>
              <dt>Protected terms</dt>
              <dd>
                {
                  preparation
                    .protected_item_extraction
                    .terms.length
                }
              </dd>
            </div>

            <div>
              <dt>Protected values</dt>
              <dd>
                {
                  preparation
                    .protected_item_extraction
                    .values.length
                }
              </dd>
            </div>
          </dl>
        </article>

        <article className="enterprise-analytics-operation">
          <div className="enterprise-analytics-operation__header">
            <span>Effective Claim Lock</span>
            <strong>
              {effectiveLock === null
                ? "No lock materialized"
                : displayMode(
                    effectiveLock.enforcement_mode
                  )}
            </strong>
          </div>

          {effectiveLock === null ? (
            <p className="enterprise-claim-lock-execution-muted">
              The server returned preparation and
              validation evidence without an effective
              Claim Lock object for this execution.
            </p>
          ) : (
            <dl>
              <div>
                <dt>Claims</dt>
                <dd>
                  {effectiveLock.claims.length}
                </dd>
              </div>

              <div>
                <dt>Terms</dt>
                <dd>
                  {effectiveLock.terms.length}
                </dd>
              </div>

              <div>
                <dt>Values</dt>
                <dd>
                  {effectiveLock.values.length}
                </dd>
              </div>
            </dl>
          )}
        </article>

        <article className="enterprise-analytics-operation">
          <div className="enterprise-analytics-operation__header">
            <span>Workspace policy execution</span>
            <strong>
              {workspacePolicy === null
                ? "Not returned"
                : workspacePolicy.policy_id}
            </strong>
          </div>

          {workspacePolicy === null ? (
            <p className="enterprise-claim-lock-execution-muted">
              No workspace-policy execution evidence
              was returned for this execution.
            </p>
          ) : (
            <dl>
              <div>
                <dt>Revision</dt>
                <dd>
                  {workspacePolicy.policy_revision}
                </dd>
              </div>

              <div>
                <dt>Policy mode</dt>
                <dd>
                  {displayMode(
                    workspacePolicy.enforcement_mode
                  )}
                </dd>
              </div>

              <div>
                <dt>Applicable terms</dt>
                <dd>
                  {
                    workspacePolicy
                      .applicable_term_ids.length
                  }
                </dd>
              </div>
            </dl>
          )}
        </article>
      </div>

      {workspacePolicy !== null &&
        workspacePolicy.applicable_term_ids.length > 0 && (
          <div className="enterprise-claim-lock-execution-policy-terms">
            <strong>
              Applicable workspace term IDs
            </strong>

            <div>
              {workspacePolicy.applicable_term_ids.map(
                (termId) => (
                  <span key={termId}>
                    {termId}
                  </span>
                )
              )}
            </div>
          </div>
        )}

      {validation.checks.length > 0 && (
        <div className="enterprise-claim-lock-execution-checks">
          <div>
            <p className="enterprise-eyebrow">
              Validation details
            </p>
            <h3>Protected-item checks</h3>
          </div>

          <div className="enterprise-claim-lock-execution-check-list">
            {validation.checks.map(
              (check, index) => (
                <article
                  className={checkTone(check)}
                  key={`${check.item_id}:${index}`}
                >
                  <div>
                    <span>
                      {displayDecision(
                        check.item_type
                      )}
                    </span>
                    <strong>
                      {check.item_id}
                    </strong>
                  </div>

                  <p>{check.expected_text}</p>

                  <footer>
                    <strong>
                      {displayDecision(
                        check.status
                      )}
                    </strong>
                    <span>{check.reason}</span>
                  </footer>
                </article>
              )
            )}
          </div>
        </div>
      )}
    </section>
  );
}
