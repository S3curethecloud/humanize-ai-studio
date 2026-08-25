# Enterprise Claim Lock Runtime Governance V2.12

## Status

This document freezes the V2.12 C6 runtime-governance contract for
Enterprise Workspace Claim Lock.

C6 integrates the workspace-scoped Claim Lock policy established by
V2.12 C2 through C5 into governed rewrite execution.

C6 does not replace the existing Claim Lock engine.

The V2.3 Claim Lock validation and enforcement contract remains
authoritative.

C6-P2 is architecture only.

This document does not authorize runtime implementation, frontend
activation, staging, commit, push, pull request, or release closure.

## Purpose

C2 through C5 made workspace Claim Lock policy administrable.

C6 makes an ACTIVE workspace policy participate in governed rewrite
execution while preserving the existing Claim Lock runtime.

Each governed rewrite must resolve one deterministic effective control
set from:

- source-derived protected claims;
- source-derived protected values;
- request-provided protected terms;
- source-applicable workspace protected terms;
- the strongest applicable enforcement mode.

The result is one effective `ClaimLock` consumed by the existing
validation and enforcement pipeline.

## Existing Authority

C6 must reuse and preserve:

- `ClaimLock`;
- `ClaimLockEnforcementMode`;
- `ClaimLockOrigin`;
- `ProtectedClaim`;
- `ProtectedTerm`;
- `ProtectedValue`;
- `ClaimLockProvenance`;
- `ClaimLockPreparationService`;
- `ClaimLockValidator`;
- `EnterpriseWorkspaceClaimLockPolicyRepository`;
- `WorkspaceAuthorizationGate`;
- existing rewrite-history Claim Lock persistence;
- `claim_lock.read`;
- `claim_lock.use`;
- `claim_lock.manage`.

The authoritative contracts remain:

- `docs/release/CLAIM_LOCK_V2_3_RELEASE.md`;
- `docs/architecture/ENTERPRISE_CLAIM_LOCK_GOVERNANCE_V2_12.md`;
- the frozen C3 through C5 policy, repository, administration, audit,
  and HTTP contracts.

No second Claim Lock validator is authorized.

No second workspace Claim Lock policy repository is authorized.

No second authorization resolver is authorized.

## Runtime Authority

C6 introduces one canonical runtime composition authority:

`EnterpriseClaimLockRuntimeService`

The runtime service must be composed from the exact existing:

- `enterprise_claim_lock_policies` repository;
- `workspace_authorization` gate;
- `claim_lock_preparation` service.

It is responsible for:

- resolving the current workspace policy after rewrite authorization;
- evaluating ACTIVE versus DISABLED policy state;
- detecting request Claim Lock customization;
- enforcing `claim_lock.use` for request customization;
- invoking existing source/request preparation;
- determining source-applicable workspace terms;
- composing workspace and request terms;
- resolving effective enforcement mode;
- constructing one effective `ClaimLock`;
- producing immutable workspace-policy execution evidence.

It is not responsible for:

- rewriting text;
- provider execution;
- Claim Lock validation;
- candidate ranking;
- section reconstruction;
- workspace policy administration.

## Runtime Context

C6 introduces one immutable execution result:

`EnterpriseClaimLockRuntimeContext`

Runtime contract version:

`enterprise-claim-lock-runtime-v1`

The runtime context must represent at least:

- request/source preparation evidence;
- effective Claim Lock, if protected items exist;
- workspace policy execution evidence, if an ACTIVE policy applies;
- whether request Claim Lock customization was requested;
- the resolved effective enforcement mode.

The runtime context is execution state.

It is not workspace policy configuration.

## Workspace Policy Execution Evidence

C6 introduces immutable execution evidence:

`EnterpriseClaimLockWorkspacePolicyExecutionEvidence`

Evidence contract version:

`enterprise-claim-lock-workspace-policy-execution-v1`

The evidence must contain:

- policy version;
- policy identifier;
- policy revision;
- workspace enforcement mode;
- applicable workspace term identifiers.

This evidence is present when an ACTIVE workspace policy was resolved
for the execution.

`applicable_term_ids` may be empty.

Workspace term lineage remains carried by canonical provenance:

`workspace-claim-lock-policy:<policy_id>:revision:<revision>`

Execution-level policy evidence supplements term provenance when policy
mode contributes but no workspace term is source-applicable.

`ClaimLock.lock_id` must not be repurposed as workspace policy identity.

## Canonical Runtime Ordering

The frozen runtime sequence begins:

1. require authorization for the underlying rewrite operation;
2. resolve the current workspace Claim Lock policy;
3. determine whether the policy is ACTIVE;
4. determine whether request Claim Lock customization was supplied;
5. if request customization was supplied, require `claim_lock.use`;
6. invoke existing source/request Claim Lock preparation;
7. determine source-applicable workspace terms;
8. compose effective terms;
9. resolve the strongest applicable enforcement mode;
10. build one effective `ClaimLock`, or `None` when no protected item
    exists.

Rewrite authorization must occur before workspace policy lookup.

## Policy Lifecycle Runtime Semantics

### ACTIVE

An ACTIVE policy:

- applies automatically;
- contributes its enforcement mode;
- contributes source-applicable workspace terms;
- produces workspace policy execution evidence.

### DISABLED

A DISABLED policy remains persisted but contributes:

- no workspace terms;
- no workspace enforcement mode;
- no workspace policy execution evidence for enforcement.

Existing request/default behavior applies.

### ARCHIVED

Archived policies are historical.

They contribute nothing to new governed executions.

### No Current Policy

No current policy contributes nothing to workspace composition.

Existing request/default Claim Lock behavior applies.

## Workspace Term Applicability

Workspace policy terms are preservation configuration.

They are not insertion requirements.

A configured workspace term becomes runtime-applicable only when it is
present in the rewrite source using the stored term matching semantics.

For `case_sensitive=True`, source applicability matching is
case-sensitive.

For `case_sensitive=False`, source applicability matching is
case-insensitive.

C6 must not introduce:

- fuzzy matching;
- semantic matching;
- stemming;
- regex workspace terms;
- wildcard workspace terms;
- LLM-based term applicability.

The runtime interpretation of the C2 union rule is therefore:

`source-applicable workspace terms UNION materialized request terms`

This preserves the V2.3 principle that Claim Lock protects source content
that must not be altered.

Claim Lock remains a preservation control.

It does not become a content-insertion engine.

## Request Claim Lock Customization

C6 preserves the existing distinction between request customization and
mandatory workspace governance.

Request Claim Lock customization is requested when either:

- at least one explicit protected term is supplied; or
- `claim_lock_enforcement_mode` is explicitly supplied.

The existing request concept:

`claim_lock_requested`

continues to mean request-level customization.

It must not be redefined to mean that an ACTIVE workspace policy applied.

Workspace policy applicability and request customization are separate runtime
facts.

## Request `claim_lock.use` Authorization

Explicit request Claim Lock customization requires:

- authorization for the underlying rewrite operation; and
- `EnterprisePermission.CLAIM_LOCK_USE`.

The canonical `WorkspaceAuthorizationGate` must perform the permission check.

If `claim_lock.use` is denied:

- generation must not occur;
- request Claim Lock controls must not be silently discarded;
- execution fails closed;
- the established rewrite authorization HTTP behavior remains `403`.

The `claim_lock.use` check must occur before generation and before any
generation-related quota mutation.

## Mandatory Workspace Governance Authorization

Mandatory ACTIVE workspace policy enforcement does not require:

`claim_lock.use`

Mandatory ACTIVE workspace policy enforcement also does not require:

`claim_lock.read`

`claim_lock.read` governs policy visibility.

`claim_lock.use` governs caller-selected Claim Lock customization.

Neither permission may become a bypass around mandatory server-side workspace
governance.

## Request Mode Transport

The raw request enforcement mode must remain optional into enterprise runtime
composition.

The runtime input is:

`ClaimLockEnforcementMode | None`

`None` means the caller did not explicitly provide a mode.

The HTTP layer must not convert omitted mode to STRICT before enterprise
composition.

Otherwise an omitted request mode would incorrectly strengthen an ACTIVE
AUDIT_ONLY workspace policy.

## Legacy V2.3 Default

When there is no ACTIVE workspace policy, existing V2.3 behavior remains
authoritative.

The legacy default enforcement mode is:

`STRICT`

Therefore:

- no workspace policy + no explicit request mode -> existing STRICT behavior;
- no workspace policy + protected terms only -> STRICT;
- no workspace policy + explicit `audit_only` -> AUDIT_ONLY;
- no workspace policy + explicit `strict` -> STRICT.

## Request Enforcement Contribution

The request contribution is resolved as follows.

### Explicit Mode

If the caller explicitly supplies a mode, that mode is the request
contribution.

### Protected Terms With Omitted Mode

If protected terms are supplied but mode is omitted, the request contribution
is:

`STRICT`

This preserves existing V2.3 behavior.

### No Request Customization

If neither protected terms nor an explicit mode is supplied, there is no
request policy contribution.

When no ACTIVE workspace policy exists, legacy runtime default behavior remains
STRICT.

## Effective Enforcement Precedence

The frozen enforcement-strength ordering is:

`STRICT > AUDIT_ONLY`

When an ACTIVE workspace policy exists, the effective mode is the strongest
applicable contribution from:

- workspace policy;
- request customization.

A request may strengthen an AUDIT_ONLY workspace policy.

A request may never downgrade a STRICT workspace policy.

Required behavior:

| Workspace mode | Request controls | Request mode | Effective mode |
| --- | --- | --- | --- |
| none / disabled | none | omitted | legacy STRICT |
| none / disabled | terms | omitted | STRICT |
| none / disabled | any | audit_only | AUDIT_ONLY |
| none / disabled | any | strict | STRICT |
| audit_only | none | omitted | AUDIT_ONLY |
| audit_only | terms | omitted | STRICT |
| audit_only | any | audit_only | AUDIT_ONLY |
| audit_only | any | strict | STRICT |
| strict | none | omitted | STRICT |
| strict | terms | omitted | STRICT |
| strict | any | audit_only | STRICT |
| strict | any | strict | STRICT |

## Existing Source and Request Preparation

C6 must continue to invoke:

`ClaimLockPreparationService`

for existing source/request preparation.

It remains responsible for:

- source semantic claim extraction;
- source literal protected-value extraction;
- request explicit protected-term materialization;
- request provenance;
- existing preparation evidence.

Enterprise workspace-policy lookup does not move into
`ClaimLockPreparationService`.

Enterprise authorization does not move into
`ClaimLockPreparationService`.

## Preparation Mode

The existing preparation service requires a concrete enforcement mode.

For source/request preparation, C6 supplies:

- the explicit request mode when present;
- otherwise the legacy STRICT default.

That preparation mode is not necessarily the final enterprise effective mode.

Enterprise precedence is resolved after request/source preparation.

## Effective Protected Claims

Protected semantic claims continue to come only from the existing preparation
pipeline.

Workspace policy does not persist semantic claims.

C6 does not create workspace semantic claims.

Existing semantic claim validation remains:

`not_evaluated`

## Effective Protected Values

Protected literal values continue to come only from deterministic source
extraction.

Workspace policy does not persist arbitrary values.

The ACTIVE workspace policy's effective enforcement mode applies to the final
effective lock containing those source-derived values.

## Effective Protected Terms

The final effective term set contains:

1. source-applicable workspace protected terms;
2. materialized request protected terms not superseded by workspace authority.

Workspace terms retain their stored:

- term identifier;
- text;
- case sensitivity;
- WORKSPACE provenance;
- policy revision source reference.

Surviving request terms retain REQUEST provenance.

## Semantic Term Collision

Term semantic identity uses canonical:

`ProtectedTerm.semantic_key()`

When a workspace term and request term are semantically equivalent:

- workspace authority wins;
- the request term is excluded;
- workspace term ID is retained;
- workspace text is retained;
- workspace case sensitivity is retained;
- workspace provenance is retained.

A request cannot weaken or override a workspace-protected term.

## Distinct Terms

Semantically different workspace and request terms are both retained.

Composition must be deterministic.

Applicable workspace terms preserve deterministic policy order.

Surviving request terms preserve deterministic preparation order.

## Identifier Integrity

The final `ClaimLock` must preserve global protected-item identifier
uniqueness across:

- claims;
- terms;
- values.

If a workspace term identifier collides with a different effective protected
item identifier, and the collision is not the same workspace-winning semantic
term, composition fails closed.

The runtime must not silently:

- rename a workspace term;
- rename a source claim;
- rename a source value;
- discard an unrelated protected item;
- alter provenance.

The bounded failure reason is:

`claim_lock_composition_conflict`

## Effective Claim Lock Construction

After deterministic composition, C6 constructs one effective:

`ClaimLock`

The effective lock contains:

- source-derived claims;
- composed effective terms;
- source-derived values;
- resolved effective enforcement mode.

Downstream validators and evaluators consume this one effective lock.

No downstream validator may independently reload workspace policy.

No downstream component may independently recompute mode precedence.

## Empty Effective Protection Set

`ClaimLock` cannot be empty.

If there are no:

- source-derived claims;
- source-derived values;
- materialized request terms;
- source-applicable workspace terms;

then:

`effective_claim_lock = None`

An ACTIVE workspace policy may still have contributed execution governance
evidence even when `effective_claim_lock` is `None`.

No synthetic protected item may be created merely to produce a non-empty lock.

## Effective Lock Identifier

`ClaimLock.lock_id` remains execution-control identity.

It must not become workspace policy identity.

If composition changes neither effective controls nor effective mode,
implementation should preserve the existing prepared Claim Lock where doing so
preserves exact V2.3 behavior.

If composition changes:

- effective protected terms; or
- effective enforcement mode;

the runtime must produce a deterministic content-derived effective lock ID.

Workspace policy identity remains represented through:

- workspace term provenance; and
- workspace policy execution evidence.

## Effective Lock Canonicalization

When a composed lock ID is required, deterministic canonicalization must
include:

- runtime composition contract version;
- effective enforcement mode;
- effective protected claims;
- effective protected terms;
- effective protected values;
- canonical provenance.

It must not depend on:

- random UUID generation;
- process identity;
- mutable current-policy lookup state;
- dictionary iteration order.

## Runtime Integrity Failures

C6 introduces the bounded runtime integrity reasons:

`claim_lock_policy_resolution_failed`

`claim_lock_composition_conflict`

Both conditions fail closed.

They indicate governance or persistence integrity failure rather than an
ordinary missing resource.

Canonical HTTP rewrite routes must map these runtime integrity failures to:

`500 Internal Server Error`

Existing authorization failures remain `403`.

Existing STRICT Claim Lock violations remain `409`.

## Single Rewrite Integration

`WorkspaceRewriteService` remains the canonical single-workspace rewrite
orchestrator.

Its C6 execution sequence becomes:

1. require `rewrite.execute`;
2. resolve `EnterpriseClaimLockRuntimeContext`;
3. perform existing quota admission;
4. execute the canonical rewrite workflow;
5. validate against `effective_claim_lock`;
6. preserve canonical V1 verification precedence;
7. apply STRICT or AUDIT_ONLY from the effective lock;
8. persist effective Claim Lock execution evidence;
9. persist workspace policy execution evidence when applicable;
10. emit existing observability evidence.

The service must not validate only the pre-composition request lock when an
enterprise effective lock exists.

## Single Rewrite Enforcement Source of Truth

When an effective Claim Lock exists, enforcement behavior derives from:

`effective_claim_lock.enforcement_mode`

The raw request mode must not remain an independent enforcement authority after
composition.

This guarantees that request AUDIT_ONLY cannot weaken workspace STRICT.

## Existing V1 Verification Precedence

C6 does not change canonical V1 verification authority.

If the canonical V1 rewrite verification already returns FAIL, that failure
remains authoritative.

Claim Lock must not replace an existing V1 failure with a separate Claim Lock
outcome.

This is a frozen V2.3 invariant.

## Voice DNA Integration

`VoiceAwareWorkspaceRewriteService` remains a wrapper around the canonical
single-rewrite service.

Voice guidance may influence:

- style;
- tone;
- presentation.

Voice guidance may not influence:

- workspace policy selection;
- Claim Lock authorization;
- protected-term composition;
- enforcement precedence;
- Claim Lock validation;
- workspace policy revision attribution.

The Voice path must inherit the same runtime context through
`WorkspaceRewriteService`.

No independent workspace policy lookup is authorized inside the Voice wrapper.

No independent Claim Lock composition service is authorized for Voice.

## Voice Policy Resolution Count

One Voice rewrite operation must resolve workspace Claim Lock policy exactly
once through the delegated canonical rewrite execution.

Voice guidance construction must not cause a second workspace policy lookup.

## Multi-Candidate Runtime Integration

`MultiCandidateWorkspaceRewriteService` remains the canonical multi-candidate
workspace orchestrator.

C6 runtime policy resolution must occur:

- after `rewrite.execute` authorization;
- before candidate generation.

One immutable enterprise Claim Lock runtime context governs the complete
candidate operation.

Every candidate must be evaluated against the same:

`effective_claim_lock`

Workspace policy must not be resolved once per candidate.

## Controlled Candidate Orchestrator Boundary

`ControlledCandidateRewriteOrchestrator` remains the candidate Claim Lock
evaluation authority.

For the canonical enterprise path, it must be able to consume the already
resolved effective Claim Lock.

It must not:

- resolve workspace policy;
- authorize `claim_lock.use`;
- recompute workspace/request precedence;
- reload policy per candidate.

Lower-level request-only behavior may remain where necessary for bounded
internal compatibility, but the canonical `V2Services` path must provide the
runtime-governed control context.

## Multi-Candidate Control Uniformity

All candidates within one multi-candidate execution must share:

- the same workspace policy revision;
- the same applicable workspace terms;
- the same request preparation;
- the same effective enforcement mode;
- the same effective Claim Lock identity.

Candidate-specific policy drift is forbidden.

## Multi-Candidate STRICT Behavior

Existing candidate Claim Lock behavior remains authoritative.

If canonical V1 candidate verification has not already failed and existing
candidate control logic detects a deterministic violation under a STRICT
effective Claim Lock, existing candidate Claim Lock failure behavior remains
in force.

C6 changes the source of effective controls.

C6 does not weaken candidate enforcement.

## Multi-Candidate History Evidence

The selected completed rewrite history must persist:

- the exact effective Claim Lock snapshot;
- selected Claim Lock validation evidence;
- effective enforcement mode;
- workspace policy execution evidence when an ACTIVE policy applied;
- existing candidate audit linkage.

History must not persist only the pre-composition request lock when workspace
governance changed effective controls.

## Long-Document Runtime Integration

`LongDocumentWorkspaceRewriteService` remains the canonical long-document
workspace orchestrator.

Its C6 execution sequence becomes:

1. require `rewrite.execute`;
2. resolve one `EnterpriseClaimLockRuntimeContext` for the complete source;
3. perform existing structure detection;
4. perform existing section planning;
5. preserve existing quota admission ordering before generation;
6. execute section rewrites;
7. evaluate against the one effective Claim Lock;
8. reconstruct the document;
9. persist long-document audit evidence;
10. emit existing observability evidence.

Workspace Claim Lock policy must not be resolved independently per section.

## Long-Document Policy Resolution Count

One long-document rewrite operation resolves workspace Claim Lock policy once.

Every rewritten section is governed by the same immutable runtime context.

A policy revision change during section processing must not alter the
in-flight execution.

## Long-Document Control Evaluator Boundary

`LongDocumentControlEvaluator` remains authoritative for:

- whole-document Claim Lock validation;
- cross-section consistency;
- canonical V1 section-failure precedence;
- existing STRICT Claim Lock failure behavior.

C6 does not add enterprise policy lookup to the evaluator.

The evaluator receives:

`effective_claim_lock`

and continues to operate only on canonical `ClaimLock` semantics.

## Long-Document Evidence Gap

Before C6, long-document audit contains Claim Lock validation evidence but does
not retain the exact Claim Lock snapshot that produced that validation.

That is insufficient for V2.12 effective execution evidence.

C6 must close this gap.

## Long-Document Audit V2

C6 introduces the next long-document audit contract version:

`long-document-audit-v2`

New C6 governed long-document audit records must include:

- the effective Claim Lock snapshot when one exists;
- workspace policy execution evidence when an ACTIVE policy applied.

Existing audit evidence remains:

- document structure;
- rewrite plan;
- reconstruction;
- Claim Lock validation;
- cross-section consistency;
- canonical V1 section-failure integrity.

## Long-Document Audit V1 Compatibility

Historical:

`long-document-audit-v1`

records must remain readable.

C6 must not require fields on historical V1 payloads that did not exist when
those records were written.

No destructive long-document audit migration is authorized.

## Long-Document Audit V2 Integrity

When a V2 long-document audit contains an effective Claim Lock:

- snapshot lock ID must equal validation lock ID;
- snapshot enforcement mode must equal validation enforcement mode.

When workspace policy execution evidence exists:

- workspace-origin effective terms must retain matching policy revision
  provenance;
- `applicable_term_ids` must correspond to the effective workspace term
  contribution;
- effective enforcement mode must not be weaker than workspace policy mode.

## Long-Document SQLite Compatibility

The canonical SQLite long-document audit repository stores audit records as
JSON payloads.

C6 must preserve this persistence model unless a later explicit architecture
review authorizes otherwise.

Existing V1 JSON payloads remain readable.

New governed writes use the V2 audit contract.

## Rewrite History Effective Claim Lock Evidence

Existing `RewriteHistoryRecord` Claim Lock fields remain authoritative:

- `claim_lock_snapshot`;
- `claim_lock_validation`;
- `claim_lock_enforcement_mode`.

The frozen V2.3 tuple invariant remains:

- all three are present; or
- all three are absent.

C6 must not weaken this invariant.

## Rewrite History Workspace Policy Evidence

C6 extends rewrite history additively with optional workspace policy execution
evidence.

Conceptually:

`claim_lock_workspace_policy`

This records the immutable workspace policy execution evidence for the
completed rewrite.

It is independent from the frozen V2.3 three-field Claim Lock tuple.

## Why Workspace Policy Evidence Is Independent

An ACTIVE workspace policy can apply to an execution while no protected item
materializes.

For example:

- workspace policy is ACTIVE;
- workspace policy contributes enforcement governance;
- no workspace term occurs in source;
- source preparation yields no protected claim or literal value;
- no request term materializes.

In that case:

- workspace policy execution evidence may be present;
- effective Claim Lock may be `None`;
- the V2.3 Claim Lock audit tuple remains fully absent.

This preserves the existing tuple invariant without fabricating an empty lock.

## Rewrite History Integrity With Workspace Policy

When both workspace policy evidence and an effective Claim Lock exist:

- history snapshot must equal the exact effective lock used for validation;
- validation lock ID must match snapshot lock ID;
- persisted enforcement mode must match snapshot mode;
- validation enforcement mode must match snapshot mode;
- workspace-origin terms must retain the contributing policy revision
  provenance;
- workspace policy `applicable_term_ids` must match effective workspace-origin
  terms.

Historical interpretation must not depend on the current workspace policy
record.

## Rewrite History SQLite Evolution

SQLite rewrite history may evolve additively with one nullable execution
evidence column.

Conceptually:

`claim_lock_workspace_policy TEXT`

Existing rows receive NULL semantics.

No existing Claim Lock history column may be repurposed.

No destructive migration is authorized.

Historical rewrite records must remain readable.

## In-Flight Policy Immutability

Workspace policy is resolved once per governed execution.

The resulting runtime context is immutable.

If an administrator updates Claim Lock policy after runtime resolution:

- the in-flight execution continues using its resolved revision;
- the next execution resolves the newer revision.

A single rewrite operation must never observe more than one workspace policy
revision.

## Historical Policy Lifecycle Changes

Completed execution evidence must remain interpretable after subsequent:

- term updates;
- enforcement-mode changes;
- policy disabling;
- policy re-enabling;
- policy archiving;
- replacement-policy creation.

Historical execution evidence must never be rebuilt from current policy state.

## API Request Compatibility

The public rewrite request continues to support:

`protected_terms`

`claim_lock_enforcement_mode`

No client-supplied workspace-policy selector is authorized.

The client must not choose:

- workspace policy ID;
- workspace policy revision;
- workspace policy lifecycle state;
- workspace enforcement override.

Workspace policy remains server-resolved authority.

## API Claim Lock Evidence Evolution

The existing:

`ClaimLockRewriteEvidence`

remains the Claim Lock response evidence surface.

C6 may evolve it additively so callers can distinguish:

- request/source preparation evidence;
- effective Claim Lock actually enforced;
- workspace policy execution evidence.

Conceptually additive response fields are:

`effective_claim_lock`

`workspace_policy`

Existing fields must remain backward compatible.

## Response Evidence Visibility

The existing:

`claim_lock_requested`

property continues to indicate request customization.

Claim Lock response evidence must be returned when either:

- request Claim Lock customization was requested; or
- an ACTIVE workspace policy applied.

Mandatory workspace governance must not be hidden merely because the caller did
not explicitly request Claim Lock controls.

## Active Policy With No Effective Lock

When an ACTIVE workspace policy applies but no protected item exists:

- workspace policy execution evidence is present;
- effective Claim Lock is absent;
- validation remains the existing no-lock PASS result;
- no synthetic protected item is created.

Response evidence must truthfully represent this state.

## Cross-Tenant Runtime Isolation

A Workspace A actor attempting a rewrite against Workspace B must fail
underlying rewrite authorization before Workspace B policy resolution.

The runtime must not expose:

- whether Workspace B has a Claim Lock policy;
- Workspace B policy status;
- Workspace B enforcement mode;
- Workspace B protected terms;
- Workspace B policy revision.

Denied runtime execution must not mutate workspace policy state.

## Policy Read Permission Boundary

Mandatory workspace policy enforcement does not require:

`claim_lock.read`

An authorized rewrite caller does not gain policy administration visibility
merely because the server enforces the policy.

Runtime enforcement and administration visibility remain separate authorities.

## Quota Boundary Preservation

C6 does not redesign enterprise quota governance.

Claim Lock runtime authorization and effective control resolution must complete
before model generation.

C6 must not:

- create duplicate quota admission;
- charge quota once per workspace policy term;
- charge quota once per candidate policy lookup;
- charge quota once per long-document section policy lookup.

## Provider and Routing Boundary

C6 does not introduce provider-specific Claim Lock behavior.

Provider routing may not:

- disable workspace Claim Lock;
- downgrade enforcement mode;
- alter effective protected terms;
- alter policy revision provenance;
- choose a different workspace policy.

Workspace governance remains provider-independent.

## Observability Boundary

Existing observability remains downstream runtime evidence.

C6 does not introduce a second observability architecture.

A Claim Lock policy-resolution or composition-integrity failure must not be
reported as successful rewrite completion.

## Canonical `V2Services` Composition

`V2Services` must compose exactly one:

`EnterpriseClaimLockRuntimeService`

using the exact existing:

`enterprise_claim_lock_policies`

repository.

It must reuse the exact canonical:

`workspace_authorization`

gate.

It must reuse the canonical:

`claim_lock_preparation`

service.

The same runtime service must govern:

- single rewrite;
- multi-candidate rewrite;
- long-document rewrite.

Voice execution inherits the single-rewrite path.

## Runtime Authority Identity Requirements

Implementation tests must prove:

- runtime policy repository identity equals the C5 policy repository object;
- runtime authorization gate identity equals canonical workspace authorization;
- runtime preparation identity equals canonical Claim Lock preparation;
- single rewrite receives the canonical runtime authority;
- multi-candidate rewrite receives the canonical runtime authority;
- long-document rewrite receives the canonical runtime authority;
- Voice does not receive an independent workspace-policy authority.

## Security Invariants

C6 implementation must preserve all of the following invariants.

1. Underlying rewrite authorization occurs before workspace policy lookup.
2. An unauthorized workspace actor cannot learn workspace Claim Lock policy
   existence through rewrite execution.
3. Explicit request Claim Lock customization requires `claim_lock.use`.
4. Mandatory ACTIVE workspace policy enforcement does not require
   `claim_lock.use`.
5. Mandatory workspace enforcement does not require `claim_lock.read`.
6. A request cannot weaken an ACTIVE workspace policy.
7. STRICT remains stronger than AUDIT_ONLY.
8. Workspace authority wins semantic workspace/request term collisions.
9. Workspace term provenance survives effective composition.
10. Workspace policy revision remains historically attributable.
11. DISABLED policy contributes no runtime controls.
12. ARCHIVED policy contributes no controls to new executions.
13. Workspace terms are preservation controls, not insertion requirements.
14. Unrelated workspace terms do not enter the effective Claim Lock.
15. Composition integrity conflicts fail closed.
16. Policy-resolution integrity failures fail closed.
17. One execution observes one immutable workspace policy revision.
18. Multi-candidate execution does not reload policy per candidate.
19. Long-document execution does not reload policy per section.
20. Voice does not establish a second workspace-policy authority.
21. Existing Claim Lock validation semantics remain unchanged.
22. Existing canonical V1 verification precedence remains unchanged.
23. Existing STRICT deterministic violation behavior remains fail closed.
24. Historical execution evidence does not depend on later policy state.
25. No second workspace Claim Lock repository is introduced.
26. No second enterprise authorization resolver is introduced.
27. No client-provided policy identity or revision is authoritative.

## Policy Resolution Failure Boundary

A runtime policy lookup that cannot be safely interpreted must fail closed.

Examples include:

- ambiguous current workspace policy state;
- repository integrity failure;
- malformed persisted policy state that cannot satisfy the frozen policy
  contract.

The runtime failure reason is:

`claim_lock_policy_resolution_failed`

Generation must not continue as though no workspace policy exists.

This failure is runtime integrity failure.

It is not equivalent to:

`policy_not_found`

from the administrative API.

## Composition Failure Boundary

A runtime composition that cannot satisfy canonical Claim Lock invariants must
fail closed.

The runtime failure reason is:

`claim_lock_composition_conflict`

Examples include incompatible protected-item identifier collisions that cannot
be resolved through the frozen workspace semantic-precedence rule.

The runtime must not repair such conflicts by silently changing protected
identity or provenance.

## Runtime Failure HTTP Semantics

Canonical rewrite HTTP routes preserve:

- authorization failures -> `403`;
- existing deterministic STRICT Claim Lock violations -> `409`;
- C6 runtime policy-resolution integrity failure -> `500`;
- C6 runtime composition integrity failure -> `500`.

C6 must not accidentally route integrity failures through generic
`ValueError` handling that represents an ordinary missing resource.

## Policy State Is Read-Only During Rewrite Execution

The C6 runtime service reads workspace policy.

It does not mutate policy.

Rewrite execution must never:

- increment policy revision;
- update policy timestamps;
- change policy lifecycle status;
- rewrite configured protected terms;
- create replacement policy;
- create administration audit mutations.

Policy administration remains exclusively within the C3-C5 administration
architecture.

## Runtime Evidence Is Not Administrative Audit

Workspace policy execution evidence proves which immutable policy revision was
evaluated for a particular rewrite.

It does not replace enterprise administrative audit.

Administrative audit continues to answer:

- who changed policy;
- what administrative action occurred;
- whether the mutation succeeded or failed.

Runtime execution evidence answers:

- which policy revision governed the rewrite;
- which workspace terms were source-applicable;
- which effective Claim Lock was enforced.

These evidence classes remain separate.

## Source Applicability Determinism

Workspace term applicability must be deterministic for a fixed:

- source text;
- policy revision;
- stored term text;
- stored case-sensitivity configuration.

Repeated evaluation of identical inputs must produce identical applicable term
identifiers.

No external model call is authorized for applicability determination.

## Effective Composition Determinism

For identical:

- source text;
- request Claim Lock controls;
- workspace policy revision;

the runtime must produce equivalent:

- request preparation;
- applicable workspace term set;
- effective enforcement mode;
- effective protected-item ordering;
- effective Claim Lock identifier;
- workspace policy execution evidence.

Random execution identifiers must not influence effective Claim Lock identity.

## Workspace Policy Update Between Executions

Given:

```text
rewrite A resolves policy revision 5
administrator publishes revision 6
rewrite B begins afterward
```

Required behavior is:

```text
rewrite A -> revision 5
rewrite B -> revision 6
```

Rewrite A must not silently transition to revision 6 after its runtime context
has been resolved.

## Request Strengthening Example

Workspace policy:

```text
status = active
mode = audit_only
```

Request:

```text
claim_lock_enforcement_mode = strict
```

Required effective mode:

```text
STRICT
```

The request strengthens workspace enforcement.

## Request Downgrade Example

Workspace policy:

```text
status = active
mode = strict
```

Request:

```text
claim_lock_enforcement_mode = audit_only
```

Required effective mode:

```text
STRICT
```

The request cannot weaken workspace enforcement.

## Terms-Only Request Example

Workspace policy:

```text
status = active
mode = audit_only
```

Request:

```text
protected_terms = ["Account Number"]
claim_lock_enforcement_mode = omitted
```

The request contribution uses the existing V2.3 default:

```text
STRICT
```

Required effective mode:

```text
STRICT
```

## Unrelated Workspace Term Example

Workspace policy term:

```text
Customer Alpha
```

Source:

```text
Please rewrite our employee PTO policy.
```

The workspace term is not source-applicable.

The effective Claim Lock must not require output to contain:

```text
Customer Alpha
```

## Applicable Workspace Term Example

Workspace policy term:

```text
Customer Alpha
```

Source:

```text
Customer Alpha renewed the agreement.
```

The workspace term is source-applicable.

The effective Claim Lock retains the stored workspace term and its policy
revision provenance.

Under effective STRICT enforcement, deterministic removal of that term is
handled by the existing validator.

## Case-Insensitive Workspace Term Example

Workspace policy term:

```text
text = Customer Alpha
case_sensitive = false
```

Source:

```text
customer alpha renewed the agreement
```

The term is source-applicable.

The effective term retains the workspace definition:

```text
text = Customer Alpha
case_sensitive = false
origin = workspace
```

Existing Claim Lock validation semantics remain authoritative.

## Mode-Only Workspace Contribution Example

Workspace policy:

```text
status = active
mode = audit_only
protected_terms = []
policy_id = policy_a
revision = 7
```

Source preparation extracts a deterministic protected value.

The effective Claim Lock contains the source-derived value and uses:

```text
AUDIT_ONLY
```

Workspace policy execution evidence records:

```text
policy_id = policy_a
revision = 7
applicable_term_ids = []
```

No synthetic workspace term is required.

## Active Policy With No Protected Item Example

Workspace policy:

```text
status = active
mode = strict
protected_terms = ["Customer Alpha"]
```

The source contains no applicable workspace term, no materialized request
term, no selected protected claim, and no deterministic protected value.

Required runtime state:

```text
workspace_policy_evidence = present
effective_claim_lock = None
```

No empty ClaimLock is constructed.

## Required Runtime Service Tests

The dedicated `EnterpriseClaimLockRuntimeService` test boundary must prove at
least:

- no-policy legacy behavior;
- disabled-policy legacy behavior;
- ACTIVE AUDIT_ONLY policy behavior;
- ACTIVE STRICT policy behavior;
- workspace policy mode with no configured terms;
- request STRICT strengthening;
- request AUDIT_ONLY downgrade prevention;
- terms-only request default STRICT behavior;
- request `claim_lock.use` authorization;
- request customization denial before generation;
- mandatory workspace policy without `claim_lock.use`;
- mandatory workspace policy without `claim_lock.read`;
- case-sensitive workspace term applicability;
- case-insensitive workspace term applicability;
- unrelated workspace term exclusion;
- applicable workspace term inclusion;
- workspace/request semantic collision;
- workspace authority preservation;
- request-only term preservation;
- source-derived protected claims retained;
- source-derived protected values retained;
- identifier conflict fail-closed behavior;
- policy-resolution failure fail-closed behavior;
- effective mode determinism;
- effective term ordering determinism;
- effective lock identity determinism;
- policy revision execution evidence;
- ACTIVE policy evidence with zero applicable terms;
- effective Claim Lock absence when no protected item exists.

## Required Single Rewrite Tests

Single-rewrite integration evidence must prove:

- exact canonical runtime service usage;
- rewrite authorization before policy lookup;
- policy resolution before generation;
- effective Claim Lock validation;
- effective enforcement mode use;
- existing V1 verification precedence;
- existing STRICT failure semantics;
- AUDIT_ONLY completed evidence;
- effective history snapshot persistence;
- workspace policy history evidence;
- no-policy backward compatibility.

## Required Voice Tests

Voice integration evidence must prove:

- Voice delegates governed execution through single rewrite;
- no independent workspace policy repository is introduced;
- no second policy resolution occurs;
- workspace term protection dominates Voice guidance;
- effective STRICT violations remain blocking;
- effective AUDIT_ONLY violations remain auditable;
- workspace policy revision evidence survives Voice execution.

## Required Multi-Candidate Tests

Multi-candidate integration evidence must prove:

- one runtime policy resolution per operation;
- one policy revision for all candidates;
- one effective Claim Lock for all candidates;
- candidate generation occurs after runtime authorization;
- existing candidate control semantics remain unchanged;
- workspace terms govern every candidate;
- request strengthening applies to all candidates;
- workspace downgrade cannot occur;
- selected history persists exact effective evidence;
- Voice-aware multi-candidate execution does not create a second Claim Lock
  policy authority.

## Required Long-Document Tests

Long-document integration evidence must prove:

- one policy resolution per complete document;
- no policy resolution per section;
- one immutable runtime context for all sections;
- source-applicable workspace terms govern relevant content;
- existing cross-section consistency remains authoritative;
- existing V1 section-failure precedence remains authoritative;
- effective Claim Lock snapshot is persisted;
- workspace policy execution evidence is persisted;
- `long-document-audit-v2` integrity is enforced;
- historical `long-document-audit-v1` records remain readable.

## Required Rewrite History Tests

Rewrite-history evidence tests must prove:

- existing three-field Claim Lock tuple integrity remains unchanged;
- effective Claim Lock snapshot round-trips;
- workspace policy execution evidence round-trips;
- historical rows without workspace policy evidence remain readable;
- ACTIVE policy with no effective lock does not violate the existing
  three-field tuple;
- policy revision evidence survives repository restart;
- later workspace policy mutation does not alter historical interpretation.

## Required SQLite Tests

SQLite evidence must prove:

- additive history migration only;
- existing history rows remain readable;
- new workspace policy execution evidence persists;
- canonical Claim Lock tuple persists unchanged;
- long-document audit V1 JSON remains readable;
- long-document audit V2 JSON round-trips;
- fresh `V2Services` composition against the same database preserves runtime
  evidence.

## Required Cross-Tenant Runtime Tests

Cross-tenant runtime tests must prove:

- foreign-workspace rewrite fails before policy disclosure;
- foreign-workspace policy existence is not leaked;
- foreign-workspace policy status is not leaked;
- foreign-workspace policy mode is not leaked;
- foreign-workspace protected terms are not leaked;
- foreign-workspace revision is not leaked;
- denial causes no policy mutation;
- denial causes no rewrite-history completion.

## Canonical Composition Identity Tests

Dependency-composition tests must prove object identity for:

- `EnterpriseClaimLockRuntimeService` policy repository and
  `V2Services.enterprise_claim_lock_policies`;
- runtime authorization gate and `V2Services.workspace_authorization`;
- runtime preparation service and `V2Services.claim_lock_preparation`.

The same runtime service instance must govern:

- single rewrite;
- multi-candidate rewrite;
- long-document rewrite.

Voice must inherit the single-rewrite service rather than receive its own
workspace-policy runtime authority.

## C3-C5 Regression Preservation

C6 implementation must not regress existing workspace policy administration.

The bounded regression must preserve:

- policy domain invariants;
- repository behavior;
- atomic administration mutation behavior;
- administration authorization;
- administration audit evidence;
- HTTP administration semantics;
- SQLite policy persistence;
- cross-tenant administration isolation;
- repository factory and dependency composition.

C6 does not redefine C3-C5 administration behavior.

## V2.3 Regression Preservation

C6 implementation must preserve existing V2.3 behavior for executions without
an ACTIVE workspace policy.

Required preservation includes:

- request explicit protected terms;
- deterministic source value extraction;
- semantic claim evidence;
- STRICT fail-closed behavior;
- AUDIT_ONLY behavior;
- Voice DNA subordination;
- history Claim Lock tuple;
- SQLite historical compatibility;
- existing HTTP `409` strict violation behavior.

## Complete C6 Regression Gate

Before C6 implementation closes, validation must include:

- dedicated runtime service tests;
- single rewrite Claim Lock regression;
- Voice Claim Lock regression;
- multi-candidate Claim Lock regression;
- long-document Claim Lock regression;
- C3-C5 Claim Lock administration regression;
- rewrite-history persistence regression;
- SQLite migration and restart regression;
- runtime cross-tenant regression;
- complete V2 API regression;
- `git diff --check`;
- protected V1 boundary inspection.

Frontend regression is required only if a later separately authorized gate
changes frontend code.

## Protected V1 Boundary

C6 does not authorize changes to protected V1 implementation merely to
simplify workspace policy integration.

If implementation review discovers that a protected V1 change is genuinely
required, C6 must stop for explicit architecture review before that change.

## C6 Implementation Preflight Requirement

C6-P2 freezes architecture.

It does not authorize production implementation.

Before implementation, C6-P3 must identify the exact:

- new runtime domain/evidence files;
- new runtime service file;
- existing integration files requiring modification;
- history/evidence model files requiring additive evolution;
- SQLite persistence files requiring additive evolution;
- API model/route files requiring additive evolution;
- dedicated and regression test files.

C6-P3 must also prove that no unnecessary file is included.

## Recommended Implementation Sequence

The recommended bounded implementation sequence is:

```text
C6-P3  implementation-file and test-boundary preflight
C6-I1  runtime context and execution evidence contracts
C6-I2  runtime composition service
C6-I3  canonical V2Services dependency composition
C6-I4  single rewrite and Voice integration
C6-I5  multi-candidate integration
C6-I6  long-document integration and audit V2
C6-I7  rewrite-history and API evidence evolution
C6-I8  SQLite persistence and restart validation
C6-I9  cross-tenant runtime validation
C6-I10 bounded and full regression
```

The exact implementation sequence may be narrowed by C6-P3.

C6-P3 may not expand the frozen architecture.

## Change-Control Boundary

Each of the following remains independently authorized:

- production source mutation;
- test creation;
- staging;
- commit;
- push;
- pull request;
- merge;
- release closure.

Completion of this architecture document does not imply authorization for any
later mutation gate.

## Frontend Boundary

C6 does not activate the Claim Lock administration frontend.

Frontend activation is a separate V2.12 milestone after backend runtime
governance is proven.

C6 may define truthful backend execution evidence required by that frontend,
but no frontend mutation is authorized by C6-P2.

## NEXUS Boundary

C6 is entirely within Humanize.

C6 does not authorize modification of:

- NEXUS source;
- NEXUS architecture;
- NEXUS runtime;
- NEXUS evidence;
- NEXUS release state.

## Explicit Non-Goals

C6 does not authorize:

- a new Claim Lock validator;
- LLM-based Claim Lock validation;
- semantic claim equivalence enforcement;
- fuzzy workspace-term matching;
- regex workspace terms;
- wildcard workspace terms;
- automatic workspace policy recommendations;
- automatic policy mutation;
- policy mutation during rewrite execution;
- organization-global Claim Lock policy;
- system-global Claim Lock policy;
- cross-workspace policy inheritance;
- provider-specific Claim Lock weakening;
- request downgrade of workspace policy;
- client-selected workspace policy identity;
- client-selected policy revision;
- physical policy deletion;
- a second policy repository;
- a second authorization resolver;
- per-candidate policy resolution;
- per-section policy resolution;
- unrelated-term content insertion;
- Claim Lock frontend activation;
- NEXUS changes.

Any expansion requires explicit architecture review.

## C6-P2 Freeze Disposition

The V2.12 C6 runtime-governance contract is frozen as follows:

Runtime authority:
EnterpriseClaimLockRuntimeService

Runtime contract:
enterprise-claim-lock-runtime-v1

Workspace policy execution evidence:
enterprise-claim-lock-workspace-policy-execution-v1

Rewrite authorization before policy lookup:
REQUIRED

ACTIVE policy:
AUTOMATICALLY APPLICABLE

DISABLED policy:
NO RUNTIME CONTRIBUTION

ARCHIVED policy:
NO NEW RUNTIME CONTRIBUTION

Workspace term configuration:
PERSISTENT POLICY CONFIGURATION

Workspace term runtime applicability:
SOURCE-MATCH REQUIRED

Claim Lock semantics:
PRESERVATION, NOT INSERTION

Request customization:
TERMS OR EXPLICIT MODE

Request customization permission:
claim_lock.use

Mandatory workspace enforcement claim_lock.use:
NOT REQUIRED

Mandatory workspace enforcement claim_lock.read:
NOT REQUIRED

Request mode transport:
OPTIONAL / OMITTED STATE PRESERVED

Legacy no-policy default:
STRICT

Terms-only request default:
STRICT

Enforcement precedence:
STRICT > AUDIT_ONLY

Request downgrade:
FORBIDDEN

Workspace/request semantic collision:
WORKSPACE WINS

Workspace provenance:
PRESERVED

Identifier conflict:
FAIL CLOSED

Composition conflict reason:
claim_lock_composition_conflict

Policy resolution failure:
FAIL CLOSED

Policy resolution reason:
claim_lock_policy_resolution_failed

Runtime integrity HTTP mapping:
500

Authorization HTTP mapping:
403 UNCHANGED

STRICT violation HTTP mapping:
409 UNCHANGED

Effective ClaimLock:
ONE PER GOVERNED EXECUTION

Policy lookup:
ONCE PER EXECUTION

Candidate policy lookup:
NOT PER CANDIDATE

Long-document policy lookup:
NOT PER SECTION

Voice policy authority:
INHERITED THROUGH SINGLE REWRITE

Existing ClaimLockValidator:
UNCHANGED

Existing ClaimLockPreparationService:
REUSED

Existing V1 verification precedence:
UNCHANGED

Rewrite history Claim Lock tuple:
UNCHANGED

Rewrite history workspace policy evidence:
ADDITIVE

Long-document new audit writes:
long-document-audit-v2

Historical long-document audit v1:
READABLE

Execution evidence:
EFFECTIVE SNAPSHOT

Policy revision attribution:
TERM PROVENANCE + EXECUTION POLICY EVIDENCE

Frontend:
OUT OF C6

NEXUS:
OUT OF SCOPE

This document is the authoritative V2.12 C6-P2 runtime-governance design
boundary.

Implementation must not expand or weaken this contract without explicit
architecture review.
