# Enterprise Claim Lock Governance V2.12

## Status

This document freezes the V2.12 Workspace Claim Lock governance contract.

V2.12 extends the existing Claim Lock runtime with workspace-scoped
administration and policy enforcement.

It does not redesign the existing Claim Lock engine.

The V2.3 Claim Lock enforcement contract remains authoritative for runtime
validation behavior.

## Scope

V2.12 introduces workspace governance around the existing Claim Lock runtime.

The authorized V2.12 scope includes:

- one authoritative Claim Lock policy per workspace;
- persistent workspace-protected terminology;
- workspace-level enforcement mode;
- deterministic composition of workspace and request Claim Lock controls;
- enterprise authorization for Claim Lock read, use, and management;
- persistent workspace Claim Lock policy state;
- administrative audit evidence;
- revision-based optimistic concurrency;
- cross-tenant isolation;
- workspace Claim Lock API administration;
- frontend Claim Lock administration;
- runtime integration with existing Claim Lock preparation and validation;
- preservation of effective Claim Lock execution evidence.

V2.12 does not authorize a new Claim Lock validation engine.

## Existing Authority

The following existing contracts remain authoritative and must be reused:

- `ClaimLock`;
- `ClaimLockEnforcementMode`;
- `ClaimLockOrigin`;
- `ProtectedClaim`;
- `ProtectedTerm`;
- `ProtectedValue`;
- `ProtectedValueKind`;
- `ClaimLockProvenance`;
- `ClaimLockPreparationService`;
- `ClaimLockValidator`;
- existing Claim Lock rewrite evidence;
- existing rewrite-history Claim Lock persistence;
- enterprise permissions:
  - `claim_lock.read`;
  - `claim_lock.use`;
  - `claim_lock.manage`.

## Workspace Policy Contract

V2.12 introduces one canonical workspace-scoped policy concept:

`EnterpriseWorkspaceClaimLockPolicy`

The policy is configuration authority.

It is not a rewrite-history record and it is not a replacement for the runtime
`ClaimLock` object.

The policy must include:

- policy contract version;
- policy identifier;
- workspace identifier;
- lifecycle status;
- enforcement mode;
- protected workspace terms;
- creator user identifier;
- creation timestamp;
- last updater user identifier;
- last update timestamp;
- monotonically increasing revision.

The initial policy contract version is:

`enterprise-workspace-claim-lock-policy-v1`

## Workspace Policy Content Boundary

V2.12 workspace policy governs:

- protected terms;
- enforcement mode.

V2.12 workspace policy does not persist arbitrary protected values or semantic
claims.

Protected values and semantic claims remain derived from source/request content
through the existing Claim Lock preparation pipeline.

This avoids stale workspace facts and avoids introducing a parallel claim
governance model.

## Policy Lifecycle

The policy lifecycle is:

- `active`;
- `disabled`;
- `archived`.

### Active

An active policy contributes mandatory workspace protections to governed
rewrites.

### Disabled

A disabled policy remains persisted and auditable.

A disabled policy contributes no runtime workspace protections.

A disabled policy may be reactivated subject to authorization and revision
checks.

### Archived

An archived policy is historical and terminal.

An archived policy contributes no runtime workspace protections.

An archived policy cannot be reactivated.

No physical policy deletion is authorized.

## Policy Cardinality

A workspace may have only one authoritative non-archived Claim Lock policy.

Only one active policy may exist for a workspace.

Parallel active policies are forbidden.

Policy configuration changes update the existing policy and increment its
revision.

Administrative history is preserved through audit evidence rather than through
competing active policy objects.

## Protected Workspace Terms

Workspace protected terms reuse the canonical `ProtectedTerm` model and its
existing semantics.

Workspace-created protected terms must use:

`ClaimLockOrigin.WORKSPACE`

Workspace term provenance must identify the contributing policy revision.

The source reference format is:

`workspace-claim-lock-policy:<policy_id>:revision:<revision>`

Request-provided protected terms remain request-origin controls.

Workspace provenance must not be erased during runtime composition.

## Runtime Term Composition

The effective protected-term set is:

`workspace protected terms UNION request protected terms`

A request may add protection.

A request may not:

- remove workspace protection;
- disable workspace protection;
- override workspace protection;
- weaken workspace protection;
- rename workspace protection;
- change workspace provenance.

For different protected term content, both terms are retained.

For semantically equivalent workspace and request terms, workspace authority
wins.

If workspace and request representations differ in case-sensitivity, the
workspace definition remains authoritative.

Request-level controls must never weaken a workspace-protected term.

## Enforcement Mode Precedence

The enforcement strength ordering is:

`STRICT > AUDIT_ONLY`

The effective mode is the strongest applicable mode across workspace and
request controls.

Required behavior:

| Workspace mode | Request mode | Effective mode |
| --- | --- | --- |
| none / disabled | none | existing request/default behavior |
| none / disabled | audit_only | audit_only |
| none / disabled | strict | strict |
| audit_only | none | audit_only |
| audit_only | audit_only | audit_only |
| audit_only | strict | strict |
| strict | none | strict |
| strict | audit_only | strict |
| strict | strict | strict |

A request may strengthen workspace enforcement.

A request may never downgrade workspace enforcement.

## Workspace Policy Applicability

An active workspace Claim Lock policy applies automatically to governed
rewrites.

Workspace enforcement does not require the request to supply Claim Lock
fields.

V2.12 must distinguish internally between:

- request Claim Lock controls being explicitly supplied;
- workspace Claim Lock policy being applicable;
- effective Claim Lock enforcement being required.

Existing public request compatibility must be preserved where possible.

## Claim Lock Use Permission

Explicit request-level Claim Lock customization requires:

- the permission required for the underlying rewrite operation; and
- `claim_lock.use`.

Mandatory workspace Claim Lock enforcement does not require the caller to hold
`claim_lock.use`.

Workspace governance is mandatory policy, not an optional capability that may
be bypassed by a caller lacking Claim Lock use authority.

## Claim Lock Administration Permissions

Existing enterprise permissions are authoritative.

Read policy operations require:

`claim_lock.read`

Policy mutations require:

`claim_lock.manage`

Policy mutation includes:

- creation;
- protected-term changes;
- enforcement-mode changes;
- enabling;
- disabling;
- archiving.

No new Claim Lock permissions are authorized in V2.12.

## Authorization Authority

Claim Lock administration must resolve authority server-side using the
canonical enterprise authorization resolver.

Client-supplied role or permission claims are not authorization evidence.

Cross-workspace authority must not be inferred from client context.

## Administrative Audit

Every Claim Lock administrative mutation must create enterprise administrative
audit evidence.

Required administrative actions include:

- Claim Lock policy creation;
- Claim Lock policy update;
- Claim Lock policy enable;
- Claim Lock policy disable;
- Claim Lock policy archive.

Mutation success must not silently survive audit persistence failure where the
established administration architecture requires atomic mutation plus audit
evidence.

The existing enterprise administration audit architecture should be reused.

## Persistence Authority

V2.12 introduces a dedicated workspace Claim Lock policy repository.

Conceptually:

`EnterpriseWorkspaceClaimLockPolicyRepository`

The repository must support the authoritative operations required by the
service contract, including:

- create;
- get by identifier;
- get for workspace;
- update.

No physical delete operation is authorized.

Workspace Claim Lock configuration must not be stored inside rewrite history.

Rewrite history remains execution evidence.

## Revision Contract

The workspace policy has a monotonically increasing revision.

All policy mutations after creation require an expected revision.

If the current revision differs from the supplied expected revision, the
mutation fails with:

`revision_conflict`

Successful updates increment revision exactly once.

A successful mutation must atomically update all policy fields associated with
that revision.

No partial policy revision is valid.

## Effective Execution Evidence

Every completed rewrite governed by Claim Lock must persist the effective Claim
Lock snapshot actually enforced for that execution.

Execution evidence must represent the merged effective controls from applicable
sources, including:

- workspace protected terms;
- request protected terms;
- source-derived protected claims;
- source-derived protected values.

Historical execution evidence must not depend on later workspace policy state.

Changing workspace policy after a rewrite must not change the interpretation of
past rewrite evidence.

## Policy Revision Linkage

Workspace policy contribution to runtime Claim Lock must remain attributable to
the contributing policy revision.

The existing `ClaimLock.lock_id` must not be repurposed for workspace policy
identity.

Policy linkage is carried through workspace term provenance using:

`workspace-claim-lock-policy:<policy_id>:revision:<revision>`

## HTTP Administration Contract

The V2.12 workspace Claim Lock administration surface is:

`GET /api/v2/workspaces/{workspace_id}/claim-lock-policy`

`POST /api/v2/workspaces/{workspace_id}/claim-lock-policy`

`PATCH /api/v2/workspaces/{workspace_id}/claim-lock-policy`

`POST /api/v2/workspaces/{workspace_id}/claim-lock-policy/enable`

`POST /api/v2/workspaces/{workspace_id}/claim-lock-policy/disable`

`POST /api/v2/workspaces/{workspace_id}/claim-lock-policy/archive`

The API represents one authoritative workspace policy resource.

A general multi-policy collection API is not authorized.

Mutating requests include `actor_user_id`.

Actor authority remains server-resolved.

## Policy Update Boundary

Policy PATCH operations may modify only:

- enforcement mode;
- protected terms.

Policy PATCH operations require:

`expected_revision`

Identity, workspace ownership, creator metadata, and creation timestamp are not
client-editable configuration fields.

## Failure Vocabulary

The bounded V2.12 administration failure vocabulary includes:

- `authorization_resolution_failed`;
- `authorization_denied`;
- `policy_not_found`;
- `policy_already_exists`;
- `policy_archived`;
- `policy_not_active`;
- `policy_already_active`;
- `policy_already_disabled`;
- `policy_scope_mismatch`;
- `revision_conflict`;
- `invalid_workspace_term`;
- `persistence_rejected`;
- `transaction_required`.

HTTP mapping:

### 403

- `authorization_resolution_failed`;
- `authorization_denied`.

### 404

- `policy_not_found`;
- `policy_scope_mismatch`.

### 409

- `policy_already_exists`;
- `policy_archived`;
- `policy_not_active`;
- `policy_already_active`;
- `policy_already_disabled`;
- `revision_conflict`.

### 422

- `invalid_workspace_term`.

### 500

- `transaction_required`.

Foreign-workspace existence must not be exposed through distinguishable error
behavior.

## Cross-Tenant Isolation

A Workspace A actor must not be able to:

- read Workspace B Claim Lock policy;
- create Workspace B Claim Lock policy;
- update Workspace B Claim Lock policy;
- enable Workspace B Claim Lock policy;
- disable Workspace B Claim Lock policy;
- archive Workspace B Claim Lock policy.

Denied mutations must preserve state.

The following must remain unchanged after denial:

- revision;
- lifecycle status;
- protected terms;
- enforcement mode;
- update timestamp;
- updater identity.

Cross-tenant protection must fail closed.

## Frontend Claim Lock Administration Boundary

The Claim Lock page may expose:

- policy status;
- enforcement mode;
- workspace-protected terms;
- term case sensitivity;
- policy revision;
- update timestamp;
- authorized administrative actions.

`claim_lock.read` permits viewing.

`claim_lock.manage` permits administrative mutation.

The V2.12 Claim Lock page does not expose arbitrary semantic-claim editing.

The page does not gain authority over unrelated rewrite-history records.

## Canonical Runtime Composition Sequence

The frozen V2.12 runtime composition sequence is:

1. Resolve authorization for the underlying rewrite operation.
2. Load the active workspace Claim Lock policy.
3. If the request supplies optional Claim Lock controls, require
   `claim_lock.use`.
4. Extract source/request claims and literal protected values through the
   existing Claim Lock preparation pipeline.
5. Merge workspace protected terms and request protected terms.
6. Resolve the strongest applicable enforcement mode.
7. Build one effective `ClaimLock`.
8. Execute the canonical rewrite workflow.
9. Run the existing `ClaimLockValidator`.
10. Preserve canonical V1 verification precedence.
11. Apply existing STRICT or AUDIT_ONLY behavior.
12. Persist the effective Claim Lock execution evidence.
13. Persist existing observability evidence.

V2.12 must integrate workspace governance ahead of the existing Claim Lock
runtime rather than replace the runtime.

## Frozen Existing Claim Lock Semantics

V2.12 must not weaken or reinterpret the frozen Claim Lock behavior established
by the existing implementation and V2.3 release contract.

The following remain frozen:

- STRICT fail-closed behavior for deterministic violations;
- AUDIT_ONLY evidence behavior;
- canonical V1 verification precedence;
- exact-literal protected-value validation;
- protected-term case-sensitivity behavior;
- semantic protected claims remaining `not_evaluated`;
- Voice DNA subordination to Claim Lock;
- Claim Lock history tuple integrity;
- backward-compatible SQLite history migration;
- existing request-level Claim Lock compatibility;
- existing strict violation HTTP semantics.

## Explicit Non-Goals

V2.12 does not authorize:

- semantic claim equivalence enforcement;
- LLM-based Claim Lock validation;
- a new Claim Lock validator version solely for workspace administration;
- weakening STRICT behavior;
- changing AUDIT_ONLY semantics;
- request downgrade of workspace policy;
- physical workspace Claim Lock policy deletion;
- multiple active workspace Claim Lock policies;
- new Claim Lock RBAC permissions;
- provider-specific Claim Lock behavior;
- cross-workspace policy inheritance;
- organization-global Claim Lock administration;
- system-global Claim Lock administration;
- regex protected terms;
- wildcard protected terms;
- automatic Claim Lock policy recommendations;
- automatic removal of workspace-protected terms.

Any expansion of these boundaries requires explicit architecture review.

## C2 Freeze Disposition

The V2.12 Workspace Claim Lock governance contract is frozen as follows:

- Policy object: FROZEN
- Policy contract version: FROZEN
- One authoritative policy per workspace: FROZEN
- Lifecycle: ACTIVE / DISABLED / ARCHIVED
- Workspace-protected content: TERMS ONLY
- Workspace provenance: REQUIRED
- Workspace/request term merge: UNION
- Collision precedence: WORKSPACE WINS
- Enforcement precedence: STRICT > AUDIT_ONLY
- Request downgrade: FORBIDDEN
- Request strengthening: ALLOWED
- Request Claim Lock customization permission: `claim_lock.use`
- Mandatory workspace policy enforcement: does not require caller
  `claim_lock.use`
- Policy read permission: `claim_lock.read`
- Policy manage permission: `claim_lock.manage`
- Persistence: DEDICATED WORKSPACE POLICY REPOSITORY
- Physical deletion: FORBIDDEN
- Revisioning: REQUIRED
- Optimistic concurrency: REQUIRED
- Administrative audit: REQUIRED
- Execution evidence: EFFECTIVE SNAPSHOT
- Historical policy linkage: PROVENANCE + REVISION
- Cross-tenant isolation: REQUIRED
- Frozen V2.3 validator and enforcement semantics: UNCHANGED

This document is the authoritative V2.12-C2 design boundary.

Implementation must not expand or weaken this contract without explicit
architecture review.
