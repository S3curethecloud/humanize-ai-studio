# Enterprise Claim Lock Runtime Implementation Boundary V2.12

## Status

This document freezes the V2.12 C6-P3 implementation boundary for
Enterprise Workspace Claim Lock runtime governance.

C6-P3 is implementation planning only.

It follows the frozen runtime-governance architecture in:

`docs/architecture/ENTERPRISE_CLAIM_LOCK_RUNTIME_GOVERNANCE_V2_12.md`

Baseline repository authority:

`main @ 777cdfb95a65ffdb9e7d969854670ec34d3b33e3`

C6-P3 does not authorize:

- production source mutation;
- test mutation;
- staging;
- commit;
- push;
- pull request;
- merge;
- frontend activation;
- release closure.

Each later mutation remains independently authorized.

## Purpose

C6-P2 freezes runtime semantics.

C6-P3 freezes the exact implementation surface permitted to realize those
semantics.

The implementation boundary must be narrow enough to prevent accidental
redesign of:

- protected V1 rewrite behavior;
- the existing Claim Lock engine;
- C3-C5 workspace Claim Lock administration;
- enterprise authorization;
- enterprise quota governance;
- provider routing;
- EvalOps;
- unrelated persistence paths;
- frontend behavior;
- NEXUS.

C6 implementation may operate only inside the allowlists established by this
document.

A file not listed in an authorized mutation surface is not implicitly
authorized.

If implementation proves that an unlisted production file is genuinely
required, work must stop for architecture review before that file is changed.

## Existing Authority

The following frozen contracts remain authoritative:

- `docs/release/CLAIM_LOCK_V2_3_RELEASE.md`;
- `docs/architecture/ENTERPRISE_CLAIM_LOCK_GOVERNANCE_V2_12.md`;
- `docs/architecture/ENTERPRISE_CLAIM_LOCK_DOMAIN_REPOSITORY_V2_12.md`;
- `docs/architecture/ENTERPRISE_CLAIM_LOCK_ADMINISTRATION_SERVICE_V2_12.md`;
- `docs/architecture/ENTERPRISE_CLAIM_LOCK_HTTP_ADMINISTRATION_API_V2_12.md`;
- `docs/architecture/ENTERPRISE_CLAIM_LOCK_RUNTIME_GOVERNANCE_V2_12.md`.

C6-P3 may narrow implementation mechanics.

C6-P3 may not expand or weaken frozen runtime semantics.

## Discovery Evidence

C6-P3A identified the runtime integration surface.

C6-P3B resolved the exact production boundary and corrected the protected V1
boundary.

C6-P3C resolved the dedicated and regression test surfaces.

The discovery established that:

- no `EnterpriseClaimLockRuntimeService` currently exists;
- no `EnterpriseClaimLockRuntimeContext` currently exists;
- no workspace-policy execution evidence model currently exists;
- `V2Services` already owns the canonical policy repository;
- `V2Services` already owns the canonical workspace authorization gate;
- `V2Services` already owns the canonical Claim Lock preparation service;
- single rewrite currently performs Claim Lock preparation directly;
- Voice delegates to single rewrite;
- multi-candidate Claim Lock preparation currently occurs inside controlled
  candidate orchestration;
- long-document Claim Lock preparation currently occurs once per document;
- HTTP routes currently default omitted mode to STRICT too early;
- rewrite history currently preserves the frozen V2.3 three-field Claim Lock
  tuple;
- SQLite rewrite history uses additive schema evolution;
- long-document audit is currently `long-document-audit-v1`;
- long-document audit persistence stores the complete audit object as JSON;
- transactional rewrite-history persistence is not the canonical governed
  rewrite-history path.

## Canonical Runtime Authority

C6 implementation introduces exactly one canonical runtime authority:

`EnterpriseClaimLockRuntimeService`

It must use the exact existing:

- `V2Services.enterprise_claim_lock_policies`;
- `V2Services.workspace_authorization`;
- `V2Services.claim_lock_preparation`.

No second workspace Claim Lock policy repository is authorized.

No second enterprise authorization resolver is authorized.

No second Claim Lock preparation architecture is authorized.

No second Claim Lock validator is authorized.

The same runtime service instance must govern:

- single rewrite;
- multi-candidate rewrite;
- long-document rewrite.

Voice must inherit governed execution through single rewrite.

## New Production Files

C6 authorizes creation of exactly these new production files:

```text
apps/api/app/v2/domain/enterprise_claim_lock_runtime.py
apps/api/app/v2/services/enterprise_claim_lock_runtime_service.py
```

## Runtime Domain File

apps/api/app/v2/domain/enterprise_claim_lock_runtime.py

may define the immutable C6 execution contracts required by C6-P2, including:

EnterpriseClaimLockRuntimeContext;
EnterpriseClaimLockWorkspacePolicyExecutionEvidence;
runtime contract version constants;
workspace-policy execution evidence version constants;
bounded runtime integrity failure representation when a domain-level type is
appropriate.

The file must not become:

a policy repository;
an authorization resolver;
a validator;
a persistence adapter;
a rewrite executor.
## Runtime Service File

apps/api/app/v2/services/enterprise_claim_lock_runtime_service.py

may define:

EnterpriseClaimLockRuntimeService

and bounded runtime integrity exceptions required by C6-P2.

The service owns:

current workspace policy resolution;
ACTIVE/DISABLED interpretation;
request customization detection;
claim_lock.use authorization for request customization;
reuse of canonical source/request preparation;
deterministic workspace-term source applicability;
workspace/request term composition;
workspace semantic precedence;
identifier-integrity enforcement;
effective mode precedence;
effective Claim Lock construction;
deterministic effective lock identity;
immutable workspace-policy execution evidence.

The service must not own:

provider execution;
rewrite execution;
Claim Lock validation;
quota mutation;
policy administration;
policy mutation;
candidate ranking;
long-document reconstruction.
## Existing Production Mutation Allowlist

C6 implementation may modify only the following existing production files:

apps/api/app/v2/api/dependencies.py
apps/api/app/v2/api/models.py
apps/api/app/v2/api/routes.py

apps/api/app/v2/services/workspace_rewrite_service.py
apps/api/app/v2/services/voice_aware_rewrite_service.py
apps/api/app/v2/services/multi_candidate_rewrite_service.py
apps/api/app/v2/services/candidate_control_enforcement.py
apps/api/app/v2/services/long_document_rewrite_service.py

apps/api/app/v2/domain/models.py
apps/api/app/v2/services/rewrite_history_service.py
apps/api/app/v2/repositories/sqlite.py

apps/api/app/v2/domain/long_document_audit.py
apps/api/app/v2/services/long_document_audit_service.py

No other existing production file is authorized by C6-P3.

## Dependency Composition Boundary

apps/api/app/v2/api/dependencies.py

may be changed only to:

construct exactly one EnterpriseClaimLockRuntimeService;
inject the existing canonical policy repository;
inject the existing canonical workspace authorization gate;
inject the existing canonical Claim Lock preparation service;
provide the same runtime authority to single rewrite;
provide the same runtime authority to multi-candidate rewrite;
provide the same runtime authority to long-document rewrite;
preserve Voice inheritance through single rewrite.

It must not create:

another policy repository;
another authorization runtime;
another preparation service;
another Claim Lock validator.
## API Model Boundary

apps/api/app/v2/api/models.py

may evolve Claim Lock response evidence additively.

The existing:

ClaimLockRewriteEvidence

remains the response evidence surface.

Permitted additive evidence includes:

effective Claim Lock;
workspace-policy execution evidence.

Existing request fields remain backward compatible.

claim_lock_requested

continues to represent request customization only.

It must not be redefined as workspace policy applicability.

## HTTP Route Boundary

apps/api/app/v2/api/routes.py

may change only as required to:

preserve omitted request enforcement mode as None into runtime
composition;
stop defaulting omitted mode to STRICT before enterprise composition;
return Claim Lock evidence when request customization exists;
return Claim Lock evidence when an ACTIVE workspace policy applies;
preserve existing authorization 403;
preserve existing deterministic STRICT violation 409;
map C6 policy-resolution integrity failure to 500;
map C6 composition-integrity failure to 500.

The routes must not accept client-selected:

policy ID;
policy revision;
workspace policy lifecycle state.
## Single Rewrite Boundary

apps/api/app/v2/services/workspace_rewrite_service.py

may change only to:

consume the canonical runtime service;
resolve one runtime context after rewrite authorization;
resolve runtime governance before quota admission and generation;
validate the effective Claim Lock;
use the effective enforcement mode;
preserve existing V1 verification precedence;
persist effective Claim Lock evidence;
persist workspace-policy execution evidence.

The service must not independently reload workspace policy.

The service must not introduce a second Claim Lock validator.

## Voice Boundary

`apps/api/app/v2/services/voice_aware_rewrite_service.py`

may change only as required to preserve optional enforcement-mode transport and
delegate governed execution through `WorkspaceRewriteService`.

Voice must not:

- receive its own workspace policy repository;
- receive its own runtime policy resolver;
- resolve workspace policy independently;
- weaken effective workspace protection.

## Multi-Candidate Boundary

`apps/api/app/v2/services/multi_candidate_rewrite_service.py`

may change only to:

- consume one canonical runtime context per operation;
- resolve governance before quota admission and candidate generation;
- provide one immutable effective Claim Lock to candidate control;
- use one immutable policy revision for all candidates;
- persist selected-history effective evidence;
- preserve existing candidate selection semantics.

`apps/api/app/v2/services/candidate_control_enforcement.py`

may change only to consume pre-resolved Claim Lock preparation/effective control
state.

Candidate control must not:

- resolve workspace policy;
- perform a second enterprise Claim Lock composition;
- independently determine workspace/request mode precedence.

All candidates in one operation must observe the same effective Claim Lock.

## Long-Document Boundary

`apps/api/app/v2/services/long_document_rewrite_service.py`

may change only to:

- resolve one runtime context for the complete source document;
- resolve governance before quota admission and generation;
- pass one effective Claim Lock to the existing control evaluator;
- preserve one policy revision for all sections;
- persist runtime governance evidence into the long-document audit.

No policy resolution per section is authorized.

The existing:

`LongDocumentControlEvaluator`

remains authoritative for deterministic Claim Lock evaluation and existing V1
section-failure precedence.

## Rewrite History Domain Boundary

`apps/api/app/v2/domain/models.py`

may add optional workspace-policy execution evidence to:

`RewriteHistoryRecord`

The frozen V2.3 Claim Lock tuple remains:

```text
claim_lock_snapshot
claim_lock_validation
claim_lock_enforcement_mode
```

Those three fields must continue to be:

all present; or
all absent.

Workspace-policy execution evidence is additive and independent of that tuple.

Therefore an ACTIVE policy may produce policy execution evidence while:

claim_lock_snapshot = None

when no protected item exists.

## Rewrite History Service Boundary

apps/api/app/v2/services/rewrite_history_service.py

may accept and persist the additive immutable workspace-policy execution
evidence.

It must not:

reload workspace policy;
infer policy revision from current state;
mutate policy;
modify the existing Claim Lock tuple contract.
## SQLite Boundary

apps/api/app/v2/repositories/sqlite.py

may evolve rewrite history only through additive migration.

The authorized new persistence concept is one nullable column equivalent to:

claim_lock_workspace_policy

The exact physical name may follow repository naming conventions, but it must
represent the frozen workspace-policy execution evidence.

Required behavior:

fresh databases contain the additive column;
existing databases receive the column through additive migration;
historical rows with NULL remain readable;
new evidence round-trips;
the existing Claim Lock tuple remains unchanged;
later policy mutations do not change historical execution interpretation.

Destructive rewrite-history migration is forbidden.

## Long-Document Audit Domain Boundary

apps/api/app/v2/domain/long_document_audit.py

may evolve long-document audit so new governed writes use:

long-document-audit-v2

V2 must support the C6 evidence required by the frozen runtime contract.

Historical:

long-document-audit-v1

records must remain readable.

V1 audit compatibility must not be removed merely to simplify the V2 model.

## Long-Document Audit Service Boundary

apps/api/app/v2/services/long_document_audit_service.py

may change only to construct new V2 audit records using already-resolved
runtime/effective evidence.

It must not resolve workspace policy itself.

It must not rerun Claim Lock composition.

## Long-Document Repository Boundary

The following file is explicitly excluded from normal C6 mutation:

apps/api/app/v2/repositories/long_document_audit.py

Reason:

the repository persists the complete audit model as JSON in the existing
payload column.

C6-P3 found no schema requirement requiring repository mutation for
long-document-audit-v2.

If implementation proves otherwise, work must stop for architecture review
before this file is changed.

## Transactional History Boundary

The following are excluded:

apps/api/app/v2/repositories/unit_of_work.py
apps/api/app/v2/services/transaction_service.py

C6-P3 found that governed rewrite execution uses the canonical
RewriteHistoryService and repository bundle.

The transactional history helper is not the canonical governed rewrite
execution path.

C6 must not modify the transactional abstraction merely for symmetry.

## Protected V1 Boundary

The complete protected V1 implementation boundary is:

apps/api/app/api/**
apps/api/app/domain/**
apps/api/app/services/**
apps/api/app/workflows/**

C6 does not authorize modification anywhere under those paths.

V2 may continue importing and invoking protected V1 authority.

If C6 implementation appears to require a protected V1 mutation, implementation
must stop for explicit architecture review.

## Frozen Claim Lock Engine Boundary

The following existing Claim Lock engine files are not authorized for C6
mutation:

apps/api/app/v2/domain/claim_lock.py
apps/api/app/v2/services/claim_lock_extractor.py
apps/api/app/v2/services/claim_lock_preparation.py
apps/api/app/v2/services/claim_lock_validator.py
apps/api/app/v2/domain/claim_lock_audit.py

The existing preparation service remains the canonical V2.3 source/request
preparation authority.

The existing validator remains the canonical deterministic enforcement
authority.

Enterprise workspace composition must wrap and reuse these authorities.

It must not rewrite them.

## Frozen C3-C5 Administration Boundary

The following files remain C3-C5 administration authority and are
regression-only for C6:

apps/api/app/v2/domain/enterprise_claim_lock_policy.py
apps/api/app/v2/repositories/enterprise_claim_lock_policies.py
apps/api/app/v2/repositories/enterprise_claim_lock_policy_admin_mutations.py
apps/api/app/v2/services/enterprise_claim_lock_admin_service.py
apps/api/app/v2/services/enterprise_claim_lock_policy_repository_factory.py

C6 runtime reads policy through the canonical repository.

C6 runtime does not change policy administration semantics.

## Existing Authorization Boundary

The following is not authorized for modification:

apps/api/app/v2/services/workspace_authorization_gate.py

C6 must reuse it exactly.

Request customization requires:

claim_lock.use

Mandatory ACTIVE workspace enforcement requires neither:

claim_lock.use; nor
claim_lock.read.
## Existing Long-Document Evaluator Boundary

The following is not authorized for C6 modification:

apps/api/app/v2/services/long_document_control_evaluator.py

It continues to consume the effective Claim Lock and preserve:

deterministic validation;
STRICT fail-closed behavior;
V1 section-failure precedence;
cross-section consistency authority.
## Provider, Routing, EvalOps, and Observability Boundary

C6 does not authorize redesign of:

provider execution;
provider catalog;
provider routing;
routing evidence;
EvalOps;
evaluation datasets;
evaluation execution;
evaluation quality gates;
observability architecture.

Existing observability may consume downstream execution evidence without
becoming a second Claim Lock authority.

No provider-specific Claim Lock weakening is authorized.

## Frontend Boundary

No frontend file is authorized by C6-P3.

Claim Lock administration frontend activation remains a separate V2.12
milestone.

## NEXUS Boundary

No NEXUS source, architecture, evidence, documentation, runtime, or release
state is authorized for modification by C6.

## New Test Files

C6 authorizes later creation, under separately approved test-mutation gates, of
exactly these new test files:

apps/api/tests/v2/test_enterprise_claim_lock_runtime_service.py
apps/api/tests/v2/test_enterprise_claim_lock_runtime_api.py

No test file is created by C6-P3 itself.

## Dedicated Runtime Service Test Contract

test_enterprise_claim_lock_runtime_service.py

must prove at least:

no-policy legacy behavior;
disabled-policy legacy behavior;
ACTIVE AUDIT_ONLY behavior;
ACTIVE STRICT behavior;
mode-only ACTIVE policy;
request STRICT strengthening;
AUDIT_ONLY downgrade prevention;
terms-only request default STRICT;
request claim_lock.use;
denial before generation;
mandatory policy without claim_lock.use;
mandatory policy without claim_lock.read;
case-sensitive applicability;
case-insensitive applicability;
unrelated workspace term exclusion;
applicable workspace term inclusion;
workspace/request semantic collision;
workspace authority preservation;
request-only term preservation;
source-derived claims retained;
source-derived values retained;
identifier conflict fail closed;
policy-resolution failure fail closed;
effective mode determinism;
effective term ordering determinism;
effective lock identity determinism;
policy revision execution evidence;
ACTIVE evidence with zero applicable terms;
no empty effective Claim Lock.
## Runtime API Test Contract

test_enterprise_claim_lock_runtime_api.py

must prove at least:

- omitted request mode reaches enterprise composition as omitted;
- request customization evidence remains backward compatible;
- ACTIVE workspace policy produces visible Claim Lock response evidence;
- ACTIVE policy with no effective lock is represented truthfully;
- request authorization denial remains `403`;
- deterministic STRICT violation remains `409`;
- policy-resolution integrity failure maps to `500`;
- composition-integrity failure maps to `500`;
- no client policy ID or revision becomes authoritative.

## Existing Test Mutation Allowlist

C6 implementation may later modify only these existing test files when required
by the corresponding frozen invariant:

```text
apps/api/tests/v2/test_service_container.py

apps/api/tests/v2/test_claim_lock_history_evidence.py
apps/api/tests/v2/test_sqlite_repositories.py

apps/api/tests/v2/test_voice_aware_rewrite_service.py
apps/api/tests/v2/test_voice_aware_rewrite_api.py
apps/api/tests/v2/test_voice_rewrite_history_evidence.py

apps/api/tests/v2/test_candidate_control_enforcement.py
apps/api/tests/v2/test_multi_candidate_rewrite_service.py
apps/api/tests/v2/test_multi_candidate_rewrite_api.py

apps/api/tests/v2/test_long_document_audit_persistence.py
apps/api/tests/v2/test_long_document_api.py

apps/api/tests/v2/test_enterprise_single_rewrite_quota_admission.py
apps/api/tests/v2/test_enterprise_multi_candidate_quota_admission.py
apps/api/tests/v2/test_enterprise_long_document_quota_admission.py

apps/api/tests/v2/test_cross_tenant_authorization_regression.py
```

Authorization of a path in this list does not require that the file be changed.

Implementation should leave a listed test file untouched when its existing
assertions already prove the required behavior.

## Service Container Test Boundary

apps/api/tests/v2/test_service_container.py

may add assertions proving:

one canonical runtime service exists;
runtime policy repository identity equals
V2Services.enterprise_claim_lock_policies;
runtime authorization identity equals
V2Services.workspace_authorization;
runtime preparation identity equals
V2Services.claim_lock_preparation;
single rewrite receives the canonical runtime service;
multi-candidate receives the same runtime service;
long-document receives the same runtime service;
Voice receives no independent policy runtime.
## History Test Boundary

apps/api/tests/v2/test_claim_lock_history_evidence.py

may evolve only to prove:

the existing three-field Claim Lock tuple remains unchanged;
workspace-policy evidence is additive;
ACTIVE policy evidence may exist while the Claim Lock tuple is absent;
effective snapshot evidence is immutable;
historical records remain valid.
## SQLite Test Boundary

apps/api/tests/v2/test_sqlite_repositories.py

may evolve only to prove:

additive column migration;
historical NULL compatibility;
workspace-policy evidence round-trip;
effective Claim Lock tuple round-trip remains unchanged;
restart persistence.
## Voice Test Boundary

The authorized Voice tests may prove:

Voice delegates through governed single rewrite;
no second workspace policy lookup exists;
workspace term protection dominates Voice guidance;
effective STRICT remains blocking;
effective AUDIT_ONLY remains auditable;
workspace policy revision survives Voice history/API evidence.
## Multi-Candidate Test Boundary

The authorized multi-candidate tests may prove:

one runtime context per operation;
one policy revision for all candidates;
one effective Claim Lock for all candidates;
runtime authorization precedes quota/generation;
candidate control consumes pre-resolved effective control;
workspace terms govern every candidate;
request strengthening applies to every candidate;
downgrade cannot occur;
selected history persists exact effective evidence.
## Long-Document Test Boundary

The authorized long-document tests may prove:

one runtime resolution per complete document;
no resolution per section;
one immutable policy revision for all sections;
existing evaluator authority remains unchanged;
V2 audit writes effective evidence;
V1 audit JSON remains readable;
API evidence truthfully exposes governed execution.
## Quota Ordering Test Boundary

The three enterprise quota-admission tests may change only to prove that Claim
Lock runtime authorization/composition occurs before quota admission and
generation.

C6 does not redesign quota calculation or enforcement.

## Cross-Tenant Test Boundary

apps/api/tests/v2/test_cross_tenant_authorization_regression.py

may evolve only to prove:

rewrite authorization occurs before policy lookup;
foreign policy existence is not leaked;
foreign status is not leaked;
foreign mode is not leaked;
foreign terms are not leaked;
foreign revision is not leaked;
denial causes no policy mutation;
denial causes no completed rewrite history.
## Regression-Only Test Boundary

The following tests are regression authorities and are not part of the normal
C6 mutation allowlist:

apps/api/tests/v2/test_claim_lock_adversarial.py
apps/api/tests/v2/test_claim_lock_domain.py
apps/api/tests/v2/test_claim_lock_extractor.py
apps/api/tests/v2/test_claim_lock_preparation.py
apps/api/tests/v2/test_claim_lock_validator.py

apps/api/tests/v2/test_enterprise_claim_lock_admin_api.py
apps/api/tests/v2/test_enterprise_claim_lock_admin_api_persistence.py
apps/api/tests/v2/test_enterprise_claim_lock_admin_cross_tenant_api.py
apps/api/tests/v2/test_enterprise_claim_lock_admin_service.py
apps/api/tests/v2/test_enterprise_claim_lock_policy_admin_mutations.py
apps/api/tests/v2/test_enterprise_claim_lock_policy_domain.py
apps/api/tests/v2/test_enterprise_claim_lock_policy_repositories.py
apps/api/tests/v2/test_enterprise_claim_lock_policy_repository_factory.py

apps/api/tests/v2/test_long_document_control_evaluator.py
apps/api/tests/v2/test_workspace_authority_convergence.py
apps/api/tests/v2/test_workspace_execution_authorization_migration.py

These tests should normally be run unchanged.

If implementation appears to require weakening one of these regression
authorities, C6 must stop for architecture review.

## C6-I1 Boundary

C6-I1 is limited to runtime context and execution evidence contracts.

Expected production scope:

apps/api/app/v2/domain/enterprise_claim_lock_runtime.py

Expected dedicated test scope:

apps/api/tests/v2/test_enterprise_claim_lock_runtime_service.py

C6-I1 must not wire runtime execution.

## C6-I2 Boundary

C6-I2 is limited to canonical runtime composition service implementation.

Expected production scope:

apps/api/app/v2/services/enterprise_claim_lock_runtime_service.py

It may consume the new C6-I1 domain contracts and frozen existing authorities.

## C6-I3 Boundary

C6-I3 is limited to canonical V2Services composition.

Expected production scope:

apps/api/app/v2/api/dependencies.py

Expected validation scope includes:

apps/api/tests/v2/test_service_container.py
## C6-I4 Boundary

C6-I4 integrates single rewrite and Voice.

Expected production scope:

apps/api/app/v2/services/workspace_rewrite_service.py
apps/api/app/v2/services/voice_aware_rewrite_service.py

Associated authorized tests are limited to the applicable single/Voice tests in
this contract.

## C6-I5 Boundary

C6-I5 integrates multi-candidate execution.

Expected production scope:

apps/api/app/v2/services/multi_candidate_rewrite_service.py
apps/api/app/v2/services/candidate_control_enforcement.py
## C6-I6 Boundary

C6-I6 integrates long-document execution and audit V2.

Expected production scope:

apps/api/app/v2/services/long_document_rewrite_service.py
apps/api/app/v2/domain/long_document_audit.py
apps/api/app/v2/services/long_document_audit_service.py
## C6-I7 Boundary

C6-I7 evolves rewrite-history and API evidence.

Expected production scope:

apps/api/app/v2/domain/models.py
apps/api/app/v2/services/rewrite_history_service.py
apps/api/app/v2/api/models.py
apps/api/app/v2/api/routes.py
## C6-I8 Boundary

C6-I8 evolves SQLite persistence and validates restart behavior.

Expected production scope:

apps/api/app/v2/repositories/sqlite.py

No destructive migration is authorized.

## C6-I9 Boundary

C6-I9 is runtime cross-tenant validation.

Production mutation should not be required merely to create C6-I9 evidence.

If a security defect is discovered, its repair must remain within this
document's production allowlist.

## C6-I10 Boundary

C6-I10 is bounded and full regression.

It must include:

dedicated runtime service tests;
runtime API tests;
single rewrite Claim Lock regression;
Voice Claim Lock regression;
multi-candidate Claim Lock regression;
long-document Claim Lock regression;
C3-C5 administration regression;
history persistence regression;
SQLite migration/restart regression;
runtime cross-tenant regression;
complete V2 API regression;
protected V1 boundary inspection;
git diff --check.
## Stop Conditions

Implementation must stop before mutation if any step appears to require:

a protected V1 file;
a frozen Claim Lock engine file;
a C3-C5 administration file;
workspace_authorization_gate.py;
long_document_control_evaluator.py;
long_document_audit.py repository mutation;
unit_of_work.py;
transaction_service.py;
provider/routing/EvalOps redesign;
frontend code;
NEXUS;
a second policy repository;
a second authorization resolver;
a second validator;
policy mutation during rewrite;
destructive SQLite migration;
per-candidate policy resolution;
per-section policy resolution;
weakening a frozen regression assertion;
any production file not explicitly listed in the mutation allowlist.

A stop condition requires explicit architecture review.

## Implementation Integrity Rules

Every C6 implementation phase must preserve:

rewrite authorization before policy lookup;
fail-closed request customization authorization;
mandatory workspace enforcement without caller bypass;
workspace semantic precedence;
STRICT stronger than AUDIT_ONLY;
preservation rather than insertion;
deterministic source applicability;
deterministic effective composition;
one immutable policy revision per execution;
unchanged existing Claim Lock validator semantics;
unchanged V1 verification precedence;
immutable historical execution evidence;
no runtime policy mutation;
no duplicate enterprise authority.
## Change-Control Boundary

C6-P3 freezes implementation scope.

It does not authorize C6-I1.

The following remain separate gates:

production source creation;
production source modification;
test creation;
test modification;
staging;
commit;
push;
pull request;
merge;
release closure.
## C6-P3 Freeze Disposition

When this document is verified and published, C6-P3 establishes:

NEW PRODUCTION FILES                2
EXISTING PRODUCTION MUTATION FILES  13
NEW TEST FILES                      2
EXISTING TEST MUTATION FILES        15

PROTECTED V1                        FROZEN
CLAIM LOCK ENGINE                   FROZEN
C3-C5 ADMINISTRATION                FROZEN
LONG-DOCUMENT REPOSITORY            FROZEN
TRANSACTIONAL HISTORY PATH          OUT OF C6
FRONTEND                            OUT OF C6
NEXUS                               OUT OF SCOPE

C6-I1 may begin only after:

this contract is structurally verified;
this contract is semantically reviewed;
this contract is staged through a separate authorization;
this contract is committed through a separate authorization;
this contract is pushed through a separate authorization;
local and remote baselines converge.

Until then:

C6_IMPLEMENTATION_AUTHORITY = NONE
