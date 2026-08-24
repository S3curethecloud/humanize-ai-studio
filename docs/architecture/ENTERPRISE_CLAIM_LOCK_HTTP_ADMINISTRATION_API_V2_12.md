# Enterprise Claim Lock HTTP Administration API V2.12

## Status

This document freezes the V2.12-C5 HTTP administration API contract for
Workspace Claim Lock governance.

C5 activates the already frozen Claim Lock administration service through the
existing V2 HTTP and dependency-container architecture.

C5 does not redesign:

- the Claim Lock policy domain;
- the Claim Lock policy repository;
- the Claim Lock atomic mutation repository;
- enterprise RBAC;
- enterprise authorization resolution;
- enterprise administration audit;
- the Claim Lock administration service;
- the Claim Lock runtime;
- the Claim Lock validator;
- rewrite execution;
- frontend Claim Lock administration.

This document is subordinate to the already frozen V2.12 governance,
domain/repository, and administration-service contracts.

Where C5 resolves an HTTP-specific ambiguity not previously fixed by those
contracts, this document becomes authoritative for the V2.12 public HTTP
surface.

## Upstream Authority

The following contracts remain authoritative:

`docs/architecture/ENTERPRISE_CLAIM_LOCK_GOVERNANCE_V2_12.md`

`docs/architecture/ENTERPRISE_CLAIM_LOCK_DOMAIN_REPOSITORY_V2_12.md`

`docs/architecture/ENTERPRISE_CLAIM_LOCK_ADMINISTRATION_SERVICE_V2_12.md`

The following implementation contracts remain authoritative:

`EnterpriseWorkspaceClaimLockPolicy`

`EnterpriseClaimLockPolicyStatus`

`EnterpriseWorkspaceClaimLockPolicyRepository`

`EnterpriseClaimLockPolicyAdminMutationRepository`

`EnterpriseClaimLockAdminService`

`EnterpriseClaimLockAdministrationError`

`ClaimLockAdministrationFailureReason`

`EnterpriseAuthorizationResolver`

`EnterpriseAdminAuditRecordingService`

`EnterprisePermission`

`ClaimLockEnforcementMode`

`ProtectedTerm`

`ClaimLockProvenance`

`ClaimLockOrigin`

C5 must consume these contracts rather than introduce parallel administration
models or authority paths.

## C5 Responsibility

C5 owns:

- public request and response models for Claim Lock policy administration;
- the six frozen workspace Claim Lock HTTP endpoints;
- translation of typed Claim Lock administration failures into HTTP semantics;
- cross-tenant HTTP non-disclosure behavior;
- Claim Lock policy repository construction from V2 persistence settings;
- Claim Lock policy administration dependency wiring;
- HTTP-level memory integration tests;
- HTTP-level SQLite restart tests;
- HTTP-level cross-tenant isolation tests;
- exhaustive typed service-failure HTTP mapping tests.

C5 does not own runtime Claim Lock composition.

## Canonical HTTP Resource

The V2.12 public administration resource is one authoritative current
non-archived Claim Lock policy for one workspace.

The canonical resource URI is:

`/api/v2/workspaces/{workspace_id}/claim-lock-policy`

The resource is workspace-scoped.

The API does not expose a general Claim Lock policy collection.

The API does not expose archived-policy history.

The API does not expose a physical delete operation.

The API does not place `policy_id` in the URI.

## Frozen HTTP Surface

The only V2.12 Claim Lock administration endpoints are:

| Method | Path | Success |
| --- | --- | --- |
| GET | `/api/v2/workspaces/{workspace_id}/claim-lock-policy` | 200 |
| POST | `/api/v2/workspaces/{workspace_id}/claim-lock-policy` | 201 |
| PATCH | `/api/v2/workspaces/{workspace_id}/claim-lock-policy` | 200 |
| POST | `/api/v2/workspaces/{workspace_id}/claim-lock-policy/enable` | 200 |
| POST | `/api/v2/workspaces/{workspace_id}/claim-lock-policy/disable` | 200 |
| POST | `/api/v2/workspaces/{workspace_id}/claim-lock-policy/archive` | 200 |

No alternate Claim Lock administration endpoint is authorized by C5.

## Workspace Identity Authority

`workspace_id` comes only from the HTTP path.

No Claim Lock administration request body may contain an authoritative
`workspace_id`.

A body-supplied workspace identifier must therefore be rejected by strict
request-model validation as an extra field.

The route passes the path-owned workspace identifier to the administration
service.

The service remains responsible for server-side authorization and workspace
scope enforcement.

## Actor Identity

GET supplies:

`actor_user_id`

as a required query parameter.

Mutating requests supply:

`actor_user_id`

in the request body.

The actor identifier is not proof of authority.

The administration service resolves enterprise authority server-side.

The API must not accept client-supplied roles or permissions.

## Public Creation Status Decision

The public C5 POST contract creates a policy as:

`active`

only.

The create request does not expose a `status` field.

The route must invoke the administration service with:

`EnterpriseClaimLockPolicyStatus.ACTIVE`

explicitly.

The API must not rely on an implicit service default for this public
lifecycle decision.

The existing C4 service capability to construct an initially disabled policy
remains an internal service capability and is not public C5 authority.

A client-supplied `status` field is invalid request input and must fail normal
Pydantic extra-field validation.

An archived policy can never be created.

A disabled policy is reached only through the explicit `/disable` lifecycle
operation.

This preserves an explicit administration audit event for the lifecycle
transition.

## Policy Identity

Creation requires a caller-provided:

`policy_id`

The identifier is bounded by the existing canonical identifier contract:

- minimum length: 1;
- maximum length: 200.

The service and domain remain responsible for canonical normalization and
identity validity.

After an archived policy, a replacement policy must use a new `policy_id`.

An archived policy identifier must never be reused as a new current policy.

## Mutation Target Selector

The C2 URI represents one workspace policy and therefore intentionally does
not contain `policy_id`.

The already frozen C4 mutation service requires `policy_id` for:

- update;
- enable;
- disable;
- archive.

C5 resolves that integration boundary by requiring `policy_id` in every
post-create mutation request body.

For those requests, `policy_id` is an immutable target selector.

It is not editable policy configuration.

Supplying `policy_id` does not authorize changing policy identity.

The service must preserve the stored policy identifier.

This design prevents the HTTP route from:

- querying the Claim Lock repository directly;
- performing an authorization-bypassing pre-read;
- deriving target identity from persistence internals;
- introducing a second policy lookup contract.

Each mutation route performs one authoritative Claim Lock administration
service operation.

## Administrative Protected-Term Input

C5 introduces one request-only model concept:

`EnterpriseClaimLockProtectedTermInput`

It contains exactly:

`term_id`

`text`

`case_sensitive`

The model must use:

`ConfigDict(extra="forbid")`

The bounded structural fields are:

`term_id: str`

with minimum length 1 and maximum length 200.

`text: str`

with minimum length 1 and maximum length 1000.

`case_sensitive: bool = True`

The request model must not contain:

- provenance;
- origin;
- source reference;
- policy revision;
- workspace identity;
- creator identity;
- updater identity;
- timestamps.

Client-provided provenance is forbidden.

The Claim Lock administration service remains the sole authority for
constructing:

`ClaimLockOrigin.WORKSPACE`

and:

`workspace-claim-lock-policy:<policy_id>:revision:<revision>`

The HTTP layer must convert request term models into the bounded plain mapping
shape required by the administration service.

The route must not construct `ProtectedTerm` domain objects or provenance
itself.

## Create Request

The canonical request model is:

`CreateEnterpriseClaimLockPolicyRequest`

It contains exactly:

`actor_user_id`

`policy_id`

`enforcement_mode`

`protected_terms`

The fields are:

`actor_user_id: str`

minimum length 1, maximum length 200.

`policy_id: str`

minimum length 1, maximum length 200.

`enforcement_mode: ClaimLockEnforcementMode`

`protected_terms: tuple[EnterpriseClaimLockProtectedTermInput, ...] = ()`

The model uses:

`ConfigDict(extra="forbid")`

The request does not contain lifecycle status.

The request does not contain workspace identity.

The request does not contain revision.

The request does not contain provenance.

The request does not contain creator/updater metadata.

The request does not contain timestamps.

Empty protected terms remain valid because the frozen workspace policy domain
allows an empty protected-term configuration.

## Update Request

The canonical request model is:

`UpdateEnterpriseClaimLockPolicyRequest`

It contains exactly:

`actor_user_id`

`policy_id`

`expected_revision`

`enforcement_mode`

`protected_terms`

The fields are:

`actor_user_id: str`

minimum length 1, maximum length 200.

`policy_id: str`

minimum length 1, maximum length 200.

`expected_revision: int`

minimum value 1.

`enforcement_mode: ClaimLockEnforcementMode`

`protected_terms: tuple[EnterpriseClaimLockProtectedTermInput, ...]`

The model uses:

`ConfigDict(extra="forbid")`

PATCH is a complete replacement of the editable Claim Lock policy
configuration.

Therefore both:

`enforcement_mode`

and:

`protected_terms`

are required.

PATCH does not provide implicit merge semantics.

PATCH does not provide term-by-term add/remove semantics.

PATCH does not mutate lifecycle status.

PATCH does not accept creator/updater metadata, timestamps, policy version,
workspace identity, or provenance.

The existing service owns revision advancement and reconstruction of all
workspace term provenance for the new revision.

## Lifecycle Request

The canonical lifecycle request model is:

`EnterpriseClaimLockPolicyLifecycleRequest`

It contains exactly:

`actor_user_id`

`policy_id`

`expected_revision`

The fields are:

`actor_user_id: str`

minimum length 1, maximum length 200.

`policy_id: str`

minimum length 1, maximum length 200.

`expected_revision: int`

minimum value 1.

The model uses:

`ConfigDict(extra="forbid")`

The same request model is reused for:

`/enable`

`/disable`

`/archive`

Lifecycle requests cannot modify enforcement mode or protected terms.

The service reconstructs workspace provenance at the new lifecycle revision.

## GET Request

GET accepts no request body.

GET requires:

`actor_user_id`

as a query parameter with:

minimum length 1;

maximum length 200.

GET delegates directly to:

`EnterpriseClaimLockAdminService.get_policy(...)`

GET requires the service-level:

`claim_lock.read`

authority.

## Canonical Response

The canonical response model is:

`EnterpriseClaimLockPolicyResponse`

It contains exactly:

`policy`

where:

`policy: EnterpriseWorkspaceClaimLockPolicy`

The HTTP layer returns the authoritative policy produced by the service.

The API must not reconstruct or independently calculate policy state.

The returned policy includes the canonical:

- policy version;
- policy identifier;
- workspace identifier;
- lifecycle status;
- enforcement mode;
- protected terms;
- workspace provenance;
- creator identity;
- creation timestamp;
- updater identity;
- update timestamp;
- revision.

## Create Route Contract

POST must:

1. bind `workspace_id` from the path;
2. validate the strict create request model;
3. convert protected-term input models into bounded plain mappings;
4. call `services.claim_lock_admin.create_policy(...)`;
5. pass the path workspace;
6. pass the caller-provided policy identifier;
7. pass enforcement mode;
8. pass protected terms;
9. explicitly pass `EnterpriseClaimLockPolicyStatus.ACTIVE`;
10. return the created authoritative policy;
11. return HTTP 201.

The route must not call the base policy repository.

The route must not construct audit evidence.

The route must not perform authorization itself.

## Update Route Contract

PATCH must:

1. bind `workspace_id` from the path;
2. validate the strict update request model;
3. convert protected-term inputs into bounded plain mappings;
4. call `services.claim_lock_admin.update_policy(...)`;
5. pass actor identity;
6. pass path workspace identity;
7. pass the immutable target `policy_id`;
8. pass `expected_revision`;
9. pass the complete editable policy configuration;
10. return the authoritative updated policy;
11. return HTTP 200.

The route performs no policy pre-read.

The route performs no repository access.

## Lifecycle Route Contract

Each lifecycle route must call exactly one corresponding service operation:

`enable_policy(...)`

`disable_policy(...)`

`archive_policy(...)`

The route passes:

- actor identity;
- path workspace identity;
- immutable target policy identifier;
- expected revision.

The route does not calculate the next revision.

The route does not reconstruct protected-term provenance.

The route does not construct administrative audit evidence.

The returned response is the authoritative mutated policy.

## Archive Response Semantics

A successful archive operation returns HTTP 200 with the newly archived policy.

After archive, the public current-policy GET returns:

HTTP 404

with:

`{"detail": "policy_not_found"}`

because archived policies are excluded from the current workspace-policy
resource.

C5 does not introduce archived-policy retrieval.

## Replacement After Archive

After archive, the workspace may create a new current policy through POST.

The replacement must use a new `policy_id`.

The replacement starts at revision 1.

The archived policy remains historical persistence/audit evidence but is not
returned by the current-policy API.

## HTTP Failure Translation

C5 introduces one route-local translation boundary:

`_claim_lock_admin_http_exception(...)`

It accepts only:

`EnterpriseClaimLockAdministrationError`

and translates the frozen typed failure reason.

The route must not translate lower-level repository exceptions directly.

The route must not expose persistence exception text.

The route must not catch broad `ValueError` and reinterpret it as policy
semantics.

The administration service is authoritative for lower-level failure
normalization.

## Frozen HTTP Failure Matrix

| Service failure | HTTP status | Public detail |
| --- | ---: | --- |
| `authorization_resolution_failed` | 403 | `authorization_resolution_failed` |
| `authorization_denied` | 403 | `authorization_denied` |
| `policy_not_found` | 404 | `policy_not_found` |
| `policy_scope_mismatch` | 404 | `policy_not_found` |
| `policy_already_exists` | 409 | `policy_already_exists` |
| `policy_archived` | 409 | `policy_archived` |
| `policy_not_active` | 409 | `policy_not_active` |
| `policy_already_active` | 409 | `policy_already_active` |
| `policy_already_disabled` | 409 | `policy_already_disabled` |
| `revision_conflict` | 409 | `revision_conflict` |
| `invalid_workspace_term` | 422 | `invalid_workspace_term` |
| `persistence_rejected` | 500 | `persistence_rejected` |
| `transaction_required` | 500 | `transaction_required` |

This matrix is exhaustive for the frozen C4 failure vocabulary.

## Persistence-Rejected HTTP Decision

C2 did not assign an explicit HTTP status to:

`persistence_rejected`

C5 freezes it as:

HTTP 500 Internal Server Error.

The public detail is:

`persistence_rejected`

The response must not contain database messages, SQLite messages, Python
exception text, filesystem paths, SQL, or other persistence implementation
details.

A persistence rejection is an internal authoritative-administration failure,
not a client conflict.

A more specific service failure must never be collapsed into
`persistence_rejected`.

## Transaction-Required HTTP Decision

`transaction_required`

maps to:

HTTP 500 Internal Server Error.

The public detail is:

`transaction_required`

The API must not fall back to non-atomic sequential persistence.

## Cross-Tenant Non-Disclosure

The service retains the internal distinction between:

`policy_not_found`

and:

`policy_scope_mismatch`

for architecture and audit semantics.

The public HTTP API must not expose that distinction.

Both failures return exactly:

HTTP 404

and:

`{"detail": "policy_not_found"}`

The status code and public detail must therefore be indistinguishable.

A caller must not be able to determine whether a supplied foreign policy
identifier exists.

Cross-tenant API tests must compare both:

- HTTP status;
- response body.

Matching status alone is insufficient proof.

## Authorization Non-Disclosure

A caller lacking authority to the requested workspace must fail before policy
mutation.

Denied mutation must preserve policy state.

No route may perform direct policy persistence before service authorization.

The HTTP layer relies on the canonical service authorization boundary.

## Request Validation

Pydantic request-model validation remains distinct from Claim Lock
administration semantic validation.

Malformed HTTP input or forbidden extra fields use normal FastAPI/Pydantic
HTTP 422 validation responses.

A syntactically valid administrative term that fails canonical Claim Lock
policy semantics is translated by the administration service to:

`invalid_workspace_term`

and returns:

HTTP 422

with:

`{"detail": "invalid_workspace_term"}`

The API must not expose internal Pydantic/domain exception text for service
semantic failures.

## Extra-Field Rejection

All new Claim Lock administration body models use:

`ConfigDict(extra="forbid")`

The API must reject client attempts to provide authority-bearing or
server-authoritative fields including:

- `workspace_id`;
- `status` on create;
- `policy_version`;
- `revision` other than `expected_revision` where authorized;
- `provenance`;
- `origin`;
- `source_reference`;
- `created_by_user_id`;
- `created_at`;
- `updated_by_user_id`;
- `updated_at`.

## Optimistic Concurrency

Every mutation after create requires:

`expected_revision`

The HTTP API does not compute or substitute a revision when the field is
missing.

A missing expected revision is request validation failure.

A stale expected revision is:

HTTP 409

with:

`{"detail": "revision_conflict"}`

Successful mutation returns the policy at exactly the next authoritative
revision established by the service/repository contract.

## Lifecycle HTTP Semantics

Enable on an already active policy returns:

HTTP 409

`policy_already_active`

Disable on an already disabled policy returns:

HTTP 409

`policy_already_disabled`

Any attempted mutation of an archived policy returns:

HTTP 409

`policy_archived`

A stale lifecycle request returns:

HTTP 409

`revision_conflict`

No lifecycle endpoint is idempotently successful when no state transition
occurs.

## Claim Lock Permission Boundary

GET administration requires:

`claim_lock.read`

POST, PATCH, enable, disable, and archive require:

`claim_lock.manage`

C5 introduces no new permission.

C5 does not require:

`claim_lock.use`

for administration.

`claim_lock.use` remains reserved for request-supplied Claim Lock
customization during rewrite execution.

## API Model File

The authorized API-model implementation file is:

`apps/api/app/v2/api/models.py`

C5 may add only the bounded Claim Lock administration request/response model
types required by this contract.

C5 must not redesign unrelated API models.

## Route File

The authorized route implementation file is:

`apps/api/app/v2/api/routes.py`

C5 extends the existing V2 router.

C5 does not create a parallel FastAPI application.

C5 does not create a separate authorization middleware.

C5 does not create a second Claim Lock administration router architecture.

## Claim Lock Policy Repository Factory

C5 requires one bounded persistence factory because the existing policy
repository has memory and SQLite implementations but no canonical
`V2PersistenceSettings` builder.

The authorized new factory file is:

`apps/api/app/v2/services/enterprise_claim_lock_policy_repository_factory.py`

The canonical builder is:

`build_enterprise_claim_lock_policy_repository(...)`

It accepts:

`V2PersistenceSettings`

It returns:

`EnterpriseWorkspaceClaimLockPolicyRepository`

For:

`PersistenceBackend.MEMORY`

it returns:

`InMemoryEnterpriseWorkspaceClaimLockPolicyRepository`

For:

`PersistenceBackend.SQLITE`

it requires a SQLite path and returns:

`SQLiteEnterpriseWorkspaceClaimLockPolicyRepository`

using that exact V2 SQLite database path.

For:

`PersistenceBackend.EXTERNAL`

C5 does not invent an external Claim Lock persistence adapter.

The factory fails closed with a bounded external-persistence-unavailable
error.

The factory must call the canonical persistence settings validation before
selecting a backend.

The factory does not construct admin audit persistence.

The factory does not construct the atomic mutation repository.

## Dependency Container Wiring

The authorized dependency implementation file is:

`apps/api/app/v2/api/dependencies.py`

`V2Services` must expose one authoritative Claim Lock policy repository:

`self.enterprise_claim_lock_policies`

constructed from:

`resolved_persistence`

`V2Services` must expose one authoritative atomic administration repository:

`self.enterprise_claim_lock_policy_admin_mutations`

constructed with:

`build_enterprise_claim_lock_policy_admin_mutation_repository(...)`

using:

`policies=self.enterprise_claim_lock_policies`

and:

`audit=self.enterprise_admin_audit.repository`

`V2Services` must expose the administration service as:

`self.claim_lock_admin`

constructed with:

`EnterpriseClaimLockAdminService(...)`

using:

`policies=self.enterprise_claim_lock_policies`

`authorization_resolver=self.enterprise_authorization.authorization_resolver`

`audit_recording=self.enterprise_admin_audit.recording`

`atomic_mutations=self.enterprise_claim_lock_policy_admin_mutations`

The same resolved V2 persistence configuration must govern the policy and
enterprise-admin-audit persistence boundaries.

For SQLite, the atomic mutation repository must therefore operate against one
compatible database boundary.

C5 must not introduce best-effort cross-database mutation behavior.

## Dependency Failure Behavior

If Claim Lock policy persistence cannot be constructed for the selected V2
backend, `V2Services` must fail closed during dependency construction.

If policy persistence and admin-audit persistence cannot satisfy the atomic
mutation repository compatibility contract, dependency construction must fail
closed.

C5 must not leave `claim_lock_admin` partially initialized.

## Existing Service Reuse

C5 must use the already published:

`apps/api/app/v2/services/enterprise_claim_lock_admin_service.py`

No C5 service redesign is authorized.

If API implementation discovers a contradiction requiring service changes,
implementation must stop and return to architecture review.

C5 must not silently change C4 to accommodate route convenience.

## Existing Repository Reuse

C5 must reuse:

`apps/api/app/v2/repositories/enterprise_claim_lock_policies.py`

and:

`apps/api/app/v2/repositories/enterprise_claim_lock_policy_admin_mutations.py`

The repository factory may instantiate those existing implementations.

It must not duplicate repository semantics.

## Administrative Audit

The route does not write audit events.

The dependency container supplies the existing enterprise admin-audit
recording and atomic repository boundaries to the administration service.

Successful mutations retain the C4 atomic policy-plus-audit guarantee.

Denied and failed mutation evidence remains governed by C4.

HTTP success must never be returned for a mutation the service rejected
because required administrative audit evidence could not be persisted.

## Persistence and Restart Authority

Memory-backed API tests prove functional HTTP composition.

SQLite-backed API tests must prove authoritative policy persistence survives
`V2Services` reconstruction against the same database path.

Required restart evidence includes:

create -> restart -> GET;

PATCH -> restart -> GET;

disable -> restart -> GET;

enable -> restart -> GET;

archive -> restart -> current GET 404;

archive -> restart -> create new policy with new ID -> restart -> GET new
policy.

Restart validation must verify policy revision, lifecycle status, enforcement
mode, protected terms, and canonical workspace provenance where applicable.

## API Test Architecture

The canonical primary API test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_admin_api.py`

It uses the established FastAPI `TestClient` and memory-backed `V2Services`
integration pattern.

It must exercise real Claim Lock administration service wiring rather than
mocking authorization and persistence for the primary behavior tests.

A separate mapping test may use a mocked `claim_lock_admin` service to
exhaustively prove every typed C4 failure maps to the frozen HTTP matrix.

## SQLite API Test Architecture

The canonical persistence test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_admin_api_persistence.py`

It constructs `V2Services` with SQLite persistence, performs HTTP
administration, reconstructs `V2Services` with the same database path, and
proves the authoritative state survives restart.

Tests must not infer persistence merely from the original in-memory service
object.

## Cross-Tenant API Test Architecture

The canonical cross-tenant test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_admin_cross_tenant_api.py`

It must prove a Workspace A actor cannot:

- read Workspace B current policy;
- create Workspace B policy;
- update Workspace B policy;
- enable Workspace B policy;
- disable Workspace B policy;
- archive Workspace B policy.

Denied mutations must preserve authoritative Workspace B state.

The test suite must additionally prove that an authorized Workspace A actor
supplying:

- an existing Workspace B policy ID;
- a nonexistent policy ID;

to a Workspace A mutation receives indistinguishable:

HTTP 404

and:

`{"detail": "policy_not_found"}`

This explicitly closes the foreign-policy existence oracle.

## Repository Factory Tests

The canonical factory test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_policy_repository_factory.py`

It must prove:

memory settings build the memory repository;

SQLite settings build the SQLite repository at the configured database path;

SQLite without a path fails closed;

external persistence fails closed because no external Claim Lock policy
adapter is authorized.

## Required API Behavior Tests

C5 API validation must include successful:

GET;

create;

PATCH;

disable;

enable;

archive;

replacement creation after archive.

It must include:

required actor validation;

extra-field rejection;

client workspace-id rejection;

client provenance rejection;

create-status rejection;

expected-revision requirement;

invalid enforcement mode;

invalid workspace term;

duplicate workspace term semantic rejection;

duplicate term identifier rejection;

policy already exists;

policy not found;

policy archived;

policy already active;

policy already disabled;

revision conflict;

authorization resolution failure;

authorization denial;

persistence rejection;

transaction-required failure;

cross-tenant denial;

cross-tenant existence non-disclosure;

state preservation after every denied/failed mutation class where state
exists.

## State Preservation

For every denied or failed mutation, HTTP tests must confirm the service
contract preserves authoritative state where applicable.

The following remain unchanged:

- policy identifier;
- workspace identifier;
- policy version;
- lifecycle status;
- enforcement mode;
- protected terms;
- provenance;
- revision;
- creator identity;
- creation timestamp;
- updater identity;
- update timestamp.

HTTP error handling must not create a second mutation path.

## No Direct Repository Access From Routes

`routes.py` must not call:

`EnterpriseWorkspaceClaimLockPolicyRepository`

directly.

It must not call:

`EnterpriseClaimLockPolicyAdminMutationRepository`

directly.

It must not construct audit events.

All administration semantics remain behind:

`services.claim_lock_admin`

## No Runtime Activation

C5 does not modify:

`WorkspaceRewriteService`

`MultiCandidateWorkspaceRewriteService`

`LongDocumentWorkspaceRewriteService`

`ClaimLockPreparationService`

`ClaimLockValidator`

rewrite history Claim Lock persistence

runtime Claim Lock composition.

An active workspace policy becoming administrable through C5 does not by
itself authorize runtime workspace-policy enforcement changes.

Runtime integration remains a subsequent V2.12 gate.

## No claim_lock.use Activation

C5 does not modify request-level Claim Lock authorization.

C5 does not add `claim_lock.use` checks to rewrite routes or rewrite services.

That enforcement remains reserved for the later runtime-integration phase.

## No Frontend Activation

C5 does not modify dashboard navigation or the Claim Lock page.

Frontend Claim Lock activation is a later V2.12 gate after the HTTP
administration contract is implemented and validated.

## No NEXUS Changes

C5 is entirely scoped to the Humanize repository.

No NEXUS repository, NEXUS architecture artifact, or NEXUS runtime is modified
by this phase.

## Authorized C5 Implementation Files

After this contract is separately approved and published, bounded C5
implementation may touch:

`apps/api/app/v2/api/models.py`

`apps/api/app/v2/api/dependencies.py`

`apps/api/app/v2/api/routes.py`

and may add:

`apps/api/app/v2/services/enterprise_claim_lock_policy_repository_factory.py`

`apps/api/tests/v2/test_enterprise_claim_lock_policy_repository_factory.py`

`apps/api/tests/v2/test_enterprise_claim_lock_admin_api.py`

`apps/api/tests/v2/test_enterprise_claim_lock_admin_api_persistence.py`

`apps/api/tests/v2/test_enterprise_claim_lock_admin_cross_tenant_api.py`

No other implementation file is authorized without a bounded amendment or a
subsequent phase gate.

## C5-P2 Freeze Disposition

The V2.12 Claim Lock HTTP administration contract is frozen as follows:

HTTP resource:
one current workspace Claim Lock policy.

HTTP endpoints:
six frozen C2 endpoints.

Create status:
ACTIVE ONLY.

Client create status field:
FORBIDDEN.

Workspace identity:
PATH AUTHORITATIVE.

Create policy identifier:
REQUIRED.

Post-create mutation policy identifier:
REQUIRED AS IMMUTABLE TARGET SELECTOR.

GET actor:
REQUIRED QUERY PARAMETER.

Mutation actor:
REQUIRED BODY FIELD.

Request extra fields:
FORBIDDEN.

Administrative protected-term input:
TERM ID + TEXT + CASE SENSITIVITY ONLY.

Client provenance:
FORBIDDEN.

PATCH semantics:
COMPLETE REPLACEMENT OF EDITABLE CONFIGURATION.

Post-create optimistic concurrency:
REQUIRED.

Response authority:
CANONICAL ENTERPRISE WORKSPACE CLAIM LOCK POLICY.

Read permission:
`claim_lock.read`.

Mutation permission:
`claim_lock.manage`.

Administration `claim_lock.use`:
NOT REQUIRED.

`policy_not_found`:
HTTP 404 / `policy_not_found`.

`policy_scope_mismatch`:
HTTP 404 / `policy_not_found`.

Cross-tenant policy existence:
NOT DISTINGUISHABLE.

Lifecycle/revision conflicts:
HTTP 409.

Invalid workspace term:
HTTP 422.

Persistence rejected:
HTTP 500.

Transaction required:
HTTP 500.

Successful create:
HTTP 201.

Successful GET/PATCH/lifecycle:
HTTP 200.

Route repository access:
FORBIDDEN.

Route audit construction:
FORBIDDEN.

Repository backend factory:
REQUIRED.

Memory persistence:
SUPPORTED.

SQLite persistence:
SUPPORTED.

External Claim Lock policy persistence:
NOT IMPLEMENTED / FAIL CLOSED.

Successful policy-plus-audit atomicity:
PRESERVED.

SQLite restart evidence:
REQUIRED.

Cross-tenant state preservation:
REQUIRED.

Runtime Claim Lock composition:
OUT OF C5.

`claim_lock.use` runtime enforcement:
OUT OF C5.

Frontend activation:
OUT OF C5.

NEXUS:
OUT OF SCOPE.

This document is the authoritative V2.12-C5-P2 HTTP administration design
boundary.

Implementation must not expand or weaken this contract without explicit
architecture review.
