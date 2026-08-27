import type {
  ClaimLock,
  ClaimLockEnforcementMode,
  ClaimLockValidationAuditSnapshot,
  ClaimLockValidationCheck,
  EnterpriseClaimLockWorkspacePolicyExecutionEvidence
} from "../api/claimLock";

interface ClaimLockPersistedEvidenceProps {
  snapshot?: ClaimLock | null;
  validation?:
    ClaimLockValidationAuditSnapshot | null;
  enforcementMode?:
    ClaimLockEnforcementMode | null;
  workspacePolicy?:
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence
    | null;
}

function displayMode(
  mode: ClaimLockEnforcementMode
): string {
  return mode === "strict"
    ? "Strict"
    : "Audit only";
}

function displayValue(
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

function provenanceLabel(
  origin: string,
  sourceReference?: string | null
): string {
  const source =
    sourceReference == null ||
    sourceReference.length === 0
      ? "no source reference persisted"
      : sourceReference;

  return `${displayValue(origin)} · ${source}`;
}

export default function ClaimLockPersistedEvidence({
  snapshot,
  validation,
  enforcementMode,
  workspacePolicy
}: ClaimLockPersistedEvidenceProps) {
  const tuplePresentCount = [
    snapshot,
    validation,
    enforcementMode
  ].filter((value) => value != null).length;

  const tupleAbsent =
    tuplePresentCount === 0;

  const tupleComplete =
    tuplePresentCount === 3;

  const tuplePartial =
    tuplePresentCount > 0 &&
    tuplePresentCount < 3;

  const persistedSnapshot =
    tupleComplete && snapshot != null
      ? snapshot
      : null;

  const persistedValidation =
    tupleComplete && validation != null
      ? validation
      : null;

  const persistedMode =
    tupleComplete && enforcementMode != null
      ? enforcementMode
      : null;

  const persistedWorkspacePolicy =
    workspacePolicy ?? null;

  if (
    tupleAbsent &&
    persistedWorkspacePolicy === null
  ) {
    return (
      <div className="enterprise-claim-lock-execution">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Claim Lock · persisted history
            </p>
            <h2>Persisted execution evidence</h2>
          </div>
        </div>

        <div className="enterprise-analytics-state">
          <div>
            <h2>
              No persisted Claim Lock evidence
            </h2>
            <p>
              This historical rewrite record does
              not contain a persisted Claim Lock
              tuple or workspace-policy execution
              evidence.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="enterprise-claim-lock-execution">
      <div className="enterprise-section__heading">
        <div>
          <p className="enterprise-eyebrow">
            Claim Lock · persisted history
          </p>
          <h2>Persisted execution evidence</h2>
        </div>

        <p>
          Evidence stored with this selected rewrite
          history record. The browser does not join
          policy state or reconstruct missing
          evidence.
        </p>
      </div>

      {tuplePartial && (
        <div className="enterprise-analytics-state">
          <div>
            <h2>
              Persisted Claim Lock tuple incomplete
            </h2>
            <p>
              An unexpected partial historical tuple
              was returned. This browser will not
              repair, compose, infer, or fabricate
              the missing persisted fields.
            </p>
          </div>
        </div>
      )}

      {tupleAbsent &&
        persistedWorkspacePolicy !== null && (
          <p className="enterprise-claim-lock-execution-muted">
            No persisted effective Claim Lock tuple
            exists for this execution. Independent
            workspace-policy execution evidence is
            shown below.
          </p>
        )}

      {persistedSnapshot !== null &&
        persistedValidation !== null &&
        persistedMode !== null && (
          <>
            <div className="enterprise-analytics-context">
              <div>
                <span>Persisted lock ID</span>
                <strong>
                  {persistedSnapshot.lock_id}
                </strong>
              </div>

              <div>
                <span>Persisted mode</span>
                <strong>
                  {displayMode(persistedMode)}
                </strong>
              </div>

              <div>
                <span>Validation decision</span>
                <strong>
                  {displayValue(
                    persistedValidation.decision
                  )}
                </strong>
              </div>

              <div>
                <span>Validation checks</span>
                <strong>
                  {
                    persistedValidation
                      .checks.length
                  }
                </strong>
              </div>
            </div>

            <div className="enterprise-claim-lock-execution-grid">
              <article className="enterprise-analytics-operation">
                <div className="enterprise-analytics-operation__header">
                  <span>
                    Persisted effective Claim Lock
                  </span>
                  <strong>
                    {displayMode(
                      persistedSnapshot
                        .enforcement_mode
                    )}
                  </strong>
                </div>

                <dl>
                  <div>
                    <dt>Claims</dt>
                    <dd>
                      {
                        persistedSnapshot
                          .claims.length
                      }
                    </dd>
                  </div>

                  <div>
                    <dt>Terms</dt>
                    <dd>
                      {
                        persistedSnapshot
                          .terms.length
                      }
                    </dd>
                  </div>

                  <div>
                    <dt>Values</dt>
                    <dd>
                      {
                        persistedSnapshot
                          .values.length
                      }
                    </dd>
                  </div>
                </dl>
              </article>

              <article className="enterprise-analytics-operation">
                <div className="enterprise-analytics-operation__header">
                  <span>
                    Persisted validation snapshot
                  </span>
                  <strong>
                    {displayValue(
                      persistedValidation.decision
                    )}
                  </strong>
                </div>

                <dl>
                  <div>
                    <dt>Lock ID</dt>
                    <dd>
                      {persistedValidation.lock_id}
                    </dd>
                  </div>

                  <div>
                    <dt>Validation mode</dt>
                    <dd>
                      {displayMode(
                        persistedValidation
                          .enforcement_mode
                      )}
                    </dd>
                  </div>

                  <div>
                    <dt>Validator</dt>
                    <dd>
                      {
                        persistedValidation
                          .validator_version
                      }
                    </dd>
                  </div>
                </dl>
              </article>

              <article className="enterprise-analytics-operation">
                <div className="enterprise-analytics-operation__header">
                  <span>
                    Persisted tuple mode
                  </span>
                  <strong>
                    {displayMode(persistedMode)}
                  </strong>
                </div>

                <p className="enterprise-claim-lock-execution-muted">
                  This value is the enforcement mode
                  stored with the historical V2.3
                  Claim Lock tuple. It is presented
                  directly, not recomputed.
                </p>
              </article>
            </div>

            {persistedSnapshot.claims.length > 0 && (
              <div className="enterprise-claim-lock-execution-checks">
                <div>
                  <p className="enterprise-eyebrow">
                    Persisted protected items
                  </p>
                  <h3>Protected claims</h3>
                </div>

                <div className="enterprise-claim-lock-execution-check-list">
                  {persistedSnapshot.claims.map(
                    (claim) => (
                      <article
                        className="enterprise-claim-lock-execution-check"
                        key={claim.claim_id}
                      >
                        <div>
                          <span>Claim</span>
                          <strong>
                            {claim.claim_id}
                          </strong>
                        </div>

                        <p>{claim.text}</p>

                        <footer>
                          <strong>
                            {displayValue(
                              claim.provenance
                                .origin
                            )}
                          </strong>
                          <span>
                            {provenanceLabel(
                              claim.provenance
                                .origin,
                              claim.provenance
                                .source_reference
                            )}
                          </span>
                        </footer>
                      </article>
                    )
                  )}
                </div>
              </div>
            )}

            {persistedSnapshot.terms.length > 0 && (
              <div className="enterprise-claim-lock-execution-checks">
                <div>
                  <p className="enterprise-eyebrow">
                    Persisted protected items
                  </p>
                  <h3>Protected terms</h3>
                </div>

                <div className="enterprise-claim-lock-execution-check-list">
                  {persistedSnapshot.terms.map(
                    (term) => (
                      <article
                        className="enterprise-claim-lock-execution-check"
                        key={term.term_id}
                      >
                        <div>
                          <span>
                            {term.case_sensitive
                              ? "Case sensitive"
                              : "Case insensitive"}
                          </span>
                          <strong>
                            {term.term_id}
                          </strong>
                        </div>

                        <p>{term.text}</p>

                        <footer>
                          <strong>
                            {displayValue(
                              term.provenance
                                .origin
                            )}
                          </strong>
                          <span>
                            {provenanceLabel(
                              term.provenance
                                .origin,
                              term.provenance
                                .source_reference
                            )}
                          </span>
                        </footer>
                      </article>
                    )
                  )}
                </div>
              </div>
            )}

            {persistedSnapshot.values.length > 0 && (
              <div className="enterprise-claim-lock-execution-checks">
                <div>
                  <p className="enterprise-eyebrow">
                    Persisted protected items
                  </p>
                  <h3>Protected values</h3>
                </div>

                <div className="enterprise-claim-lock-execution-check-list">
                  {persistedSnapshot.values.map(
                    (value) => (
                      <article
                        className="enterprise-claim-lock-execution-check"
                        key={value.value_id}
                      >
                        <div>
                          <span>
                            {displayValue(
                              value.kind
                            )}
                          </span>
                          <strong>
                            {value.value_id}
                          </strong>
                        </div>

                        <p>{value.value}</p>

                        <footer>
                          <strong>
                            {displayValue(
                              value.provenance
                                .origin
                            )}
                          </strong>
                          <span>
                            {provenanceLabel(
                              value.provenance
                                .origin,
                              value.provenance
                                .source_reference
                            )}
                          </span>
                        </footer>
                      </article>
                    )
                  )}
                </div>
              </div>
            )}

            {persistedValidation.checks.length >
              0 && (
              <div className="enterprise-claim-lock-execution-checks">
                <div>
                  <p className="enterprise-eyebrow">
                    Persisted validation
                  </p>
                  <h3>Protected-item checks</h3>
                </div>

                <div className="enterprise-claim-lock-execution-check-list">
                  {persistedValidation.checks.map(
                    (check, index) => (
                      <article
                        className={checkTone(check)}
                        key={`${check.item_id}:${index}`}
                      >
                        <div>
                          <span>
                            {displayValue(
                              check.item_type
                            )}
                          </span>
                          <strong>
                            {check.item_id}
                          </strong>
                        </div>

                        <p>
                          {check.expected_text}
                        </p>

                        <footer>
                          <strong>
                            {displayValue(
                              check.status
                            )}
                          </strong>
                          <span>
                            {check.reason}
                          </span>
                        </footer>
                      </article>
                    )
                  )}
                </div>
              </div>
            )}
          </>
        )}

      <div className="enterprise-claim-lock-execution-grid">
        <article className="enterprise-analytics-operation">
          <div className="enterprise-analytics-operation__header">
            <span>
              Persisted workspace-policy execution
            </span>
            <strong>
              {persistedWorkspacePolicy === null
                ? "Not persisted"
                : persistedWorkspacePolicy
                    .policy_id}
            </strong>
          </div>

          {persistedWorkspacePolicy === null ? (
            <p className="enterprise-claim-lock-execution-muted">
              No workspace-policy execution evidence
              was persisted for this historical
              rewrite.
            </p>
          ) : (
            <dl>
              <div>
                <dt>Revision</dt>
                <dd>
                  {
                    persistedWorkspacePolicy
                      .policy_revision
                  }
                </dd>
              </div>

              <div>
                <dt>Policy mode</dt>
                <dd>
                  {displayMode(
                    persistedWorkspacePolicy
                      .enforcement_mode
                  )}
                </dd>
              </div>

              <div>
                <dt>Applicable terms</dt>
                <dd>
                  {
                    persistedWorkspacePolicy
                      .applicable_term_ids
                      .length
                  }
                </dd>
              </div>
            </dl>
          )}
        </article>
      </div>

      {persistedWorkspacePolicy !== null &&
        persistedWorkspacePolicy
          .applicable_term_ids.length > 0 && (
          <div className="enterprise-claim-lock-execution-policy-terms">
            <strong>
              Persisted applicable workspace term IDs
            </strong>

            <div>
              {persistedWorkspacePolicy
                .applicable_term_ids.map(
                  (termId) => (
                    <span key={termId}>
                      {termId}
                    </span>
                  )
                )}
            </div>
          </div>
        )}
    </div>
  );
}
