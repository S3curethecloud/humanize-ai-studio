# Enterprise Claim Lock Administration Service V2.12

## Status

This document freezes the V2.12 Claim Lock enterprise administration service
contract.

It refines the already frozen V2.12 Workspace Claim Lock governance and
domain/repository contracts.

It does not redesign:

- the existing Claim Lock runtime;
- the Claim Lock validator;
- enterprise RBAC;
- enterprise authorization resolution;
- enterprise admin-audit persistence;
- the Claim Lock policy repository;
- the Claim Lock atomic mutation repository.

The administration service is the authoritative boundary between enterprise
administrative intent and Claim Lock policy persistence.

## Upstream Authority

The following existing contracts remain authoritative:

- `ENTERPRISE_CLAIM_LOCK_GOVERNANCE_V2_12.md`;
- `ENTERPRISE_CLAIM_LOCK_DOMAIN_REPOSITORY_V2_12.md`;
- `EnterpriseWorkspaceClaimLockPolicy`;
- `EnterpriseClaimLockPolicyStatus`;
- `EnterpriseWorkspaceClaimLockPolicyRepository`;
- `EnterpriseClaimLockPolicyAdminMutationRepository`;
- `EnterpriseAdminAuditAction`;
- `EnterpriseAdminAuditOutcome`;
- `EnterpriseAdminAuditRecordingService`;
- `EnterpriseAuthorizationResolver`;
- `EnterprisePermission`;
- `ProtectedTerm`;
- `ClaimLockProvenance`;
- `ClaimLockOrigin`;
- `ClaimLockEnforcementMode`.

C4 must consume these contracts rather than introduce parallel models.

## Service File

The bounded service implementation file is:

`apps/api/app/v2/services/enterprise_claim_lock_admin_service.py`

The bounded service test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_admin_service.py`

No HTTP route implementation is authorized by C4.

No rewrite-runtime integration is authorized by C4.

## Service Responsibility

The Claim Lock administration service owns:

- enterprise authorization checks for Claim Lock administration;
- workspace-scope enforcement;
- policy lifecycle operation semantics;
- canonical workspace protected-term construction;
- canonical workspace provenance;
- revision advancement;
- administrative audit action selection;
- administrative audit outcome selection;
- successful atomic policy-plus-audit mutation;
- denied and failed administrative audit recording;
- translation of lower-level domain/repository failures into stable
  administration failure reasons.

The service does not own:

- HTTP status mapping;
- request-model validation;
- frontend behavior;
- rewrite execution;
- runtime Claim Lock composition;
- `claim_lock.use` enforcement;
- Claim Lock validation;
- rewrite-history persistence.

## Service Type

The canonical service is:

`EnterpriseClaimLockAdminService`

Conceptually:

```python
class EnterpriseClaimLockAdminService:
    def get_policy(...):
        ...

    def create_policy(...):
        ...

    def update_policy(...):
        ...

    def enable_policy(...):
        ...

    def disable_policy(...):
        ...

    def archive_policy(...):
        ...

The exact Python signatures may be implemented within this frozen semantic
boundary.

Administration Failure Type

The service must expose one typed administration exception:

EnterpriseClaimLockAdministrationError

The exception must carry a stable failure reason.

The failure reason enum is:

ClaimLockAdministrationFailureReason

The frozen failure values are:

authorization_resolution_failed;
authorization_denied;
policy_not_found;
policy_already_exists;
policy_archived;
policy_not_active;
policy_already_active;
policy_already_disabled;
policy_scope_mismatch;
revision_conflict;
invalid_workspace_term;
persistence_rejected;
transaction_required.

No route-specific HTTP exception belongs in the service.

Authorization Boundary

All Claim Lock administration authority is resolved server-side using the
canonical enterprise authorization resolver.

Client-supplied roles, permissions, or workspace authority are not trusted.

Read

get_policy(...) requires:

EnterprisePermission.CLAIM_LOCK_READ

which corresponds to:

claim_lock.read

Mutation

The following operations require:

EnterprisePermission.CLAIM_LOCK_MANAGE

which corresponds to:

claim_lock.manage

Operations:

create policy;
update policy;
enable policy;
disable policy;
archive policy.

No new Claim Lock permission is introduced.

claim_lock.use Boundary

claim_lock.use is explicitly outside this administration service.

claim_lock.use governs request-supplied Claim Lock customization during
rewrite execution.

It must not be required merely because an active workspace Claim Lock policy
exists.

Mandatory workspace policy enforcement remains independent of caller
claim_lock.use authority.

Runtime enforcement of claim_lock.use is reserved for the later rewrite
integration phase.

Authorization Resolution Failure

If enterprise authorization cannot be resolved, the service raises:

authorization_resolution_failed

The service must fail closed.

The mutation must not occur.

The existing authoritative policy state must remain unchanged.

Authorization Denial

If authorization resolves but the actor does not hold the required permission,
the service raises:

authorization_denied

The mutation must not occur.

The existing authoritative policy state must remain unchanged.

Cross-Tenant Isolation

A policy from another workspace must never become administratively accessible
through a workspace-scoped operation.

The service must not expose foreign-workspace policy existence through
distinguishable behavior.

For workspace-scoped reads and mutations, a foreign-workspace policy is treated
as unavailable to the caller.

Where an identifier-based internal lookup returns a policy whose
workspace_id differs from the requested workspace, the service raises:

policy_scope_mismatch

External HTTP mapping remains the responsibility of the later API layer.

C2 requires both:

policy_not_found;
policy_scope_mismatch;

to map to HTTP 404 so cross-tenant existence is not leaked.

Read Contract

get_policy(...) must:

require claim_lock.read;
query the authoritative current workspace policy;
return the current non-archived policy if present;
raise policy_not_found if no current policy exists.

Archived historical policy retrieval is not part of the V2.12 public
workspace-policy administration surface.

The service does not expose a multi-policy history collection.

Create Contract

create_policy(...) must:

require claim_lock.manage;
establish policy identity;
bind the policy to the requested workspace;
construct canonical workspace protected terms;
construct revision-1 workspace provenance;
set the requested initial enforcement mode;
set the supported initial lifecycle status;
set authoritative creator/updater identity and timestamps;
build a successful CLAIM_LOCK_POLICY_CREATE audit event;
persist policy and successful audit evidence atomically.

Successful creation starts at:

revision = 1

The initial policy must not be archived.

Creation must fail when a current non-archived workspace policy already exists.

That condition maps to:

policy_already_exists

Policy Identity

The service must not permit the caller to alter an existing policy identifier.

A new policy created after a previous policy has been archived must receive a
new policy identifier.

Archived policy identity is never reused as a new active administrative
authority.

Workspace Protected-Term Input

Administrative input may express protected-term configuration containing only
the bounded data required to construct a canonical ProtectedTerm.

Conceptually:

term_id;
text;
case_sensitive.

Client input must not provide authoritative workspace provenance.

The service constructs provenance.

Canonical Workspace Provenance

All workspace-protected terms persisted by the service must use:

ClaimLockOrigin.WORKSPACE

The source reference format is:

workspace-claim-lock-policy:<policy_id>:revision:<revision>

For create:

revision = 1

For every successful update or lifecycle mutation:

revision = current revision + 1

The provenance revision must match the policy revision being persisted.

The service must not preserve stale provenance from a previous revision when
constructing a new policy revision.

Invalid Workspace Term

A workspace term that cannot be represented by the canonical ProtectedTerm
contract must fail as:

invalid_workspace_term

Examples include domain-invalid term identifiers, text, duplicate identity, or
duplicate semantic content according to the existing Claim Lock domain rules.

The service must not silently normalize invalid administrative configuration
into a different governance meaning.

Update Contract

update_policy(...) may modify only:

enforcement mode;
protected terms.

It must require:

expected_revision

The service must:

require claim_lock.manage;
load the current policy;
confirm workspace scope;
reject archived policy mutation;
validate expected_revision;
calculate new_revision = current_revision + 1;
construct all workspace term provenance for new_revision;
preserve immutable policy identity and creation metadata;
update updater identity and update timestamp;
build a successful CLAIM_LOCK_POLICY_UPDATE audit event;
invoke the atomic update mutation.

Ordinary PATCH semantics may preserve the current lifecycle status.

Therefore:

active -> active

is valid for a normal configuration update.

And:

disabled -> disabled

is valid for a normal configuration update.

Same-status PATCH must not be confused with semantic enable/disable operations.

Revision Contract

All post-create mutations require optimistic concurrency.

The supplied:

expected_revision

must equal the currently persisted revision.

A mismatch fails as:

revision_conflict

A successful mutation increments the revision exactly once.

The successful policy revision is:

expected_revision + 1

No skipped revision is valid.

No blind update is authorized.

Archived Policy Contract

An archived policy is terminal.

Any attempt to modify an archived policy fails as:

policy_archived

This includes:

PATCH update;
enable;
disable;
archive again as an ordinary mutation.

An archived policy must never become active or disabled again.

Enable Contract

enable_policy(...) must:

require claim_lock.manage;
load the current workspace policy;
confirm workspace scope;
require expected_revision;
reject archived policy;
reject already-active policy;
require the current status to be disabled;
construct revision-updated term provenance;
change status to active;
increment revision exactly once;
update updater identity and timestamp;
build CLAIM_LOCK_POLICY_ENABLE;
persist policy and successful audit evidence atomically.

If already active:

policy_already_active

If archived:

policy_archived

If no current policy exists:

policy_not_found

Disable Contract

disable_policy(...) must:

require claim_lock.manage;
load the current workspace policy;
confirm workspace scope;
require expected_revision;
reject archived policy;
reject already-disabled policy;
require the current status to be active;
construct revision-updated term provenance;
change status to disabled;
increment revision exactly once;
update updater identity and timestamp;
build CLAIM_LOCK_POLICY_DISABLE;
persist policy and successful audit evidence atomically.

If already disabled:

policy_already_disabled

If archived:

policy_archived

If no current policy exists:

policy_not_found

Archive Contract

archive_policy(...) must:

require claim_lock.manage;
load the current workspace policy;
confirm workspace scope;
require expected_revision;
reject an already archived policy;
require the current policy to be active or disabled;
construct revision-updated term provenance;
change status to archived;
increment revision exactly once;
update updater identity and timestamp;
build CLAIM_LOCK_POLICY_ARCHIVE;
persist policy and successful audit evidence atomically.

Archive is terminal.

No physical delete is authorized.

policy_not_active

policy_not_active is reserved for an administrative operation that
semantically requires an active policy but encounters a non-active current
policy and is not more precisely represented by another frozen lifecycle
failure.

The service must prefer the more specific frozen reason where one exists.

For example:

enable on active -> policy_already_active;
disable on disabled -> policy_already_disabled;
any mutation on archived -> policy_archived.

The service must not invent additional lifecycle failure vocabulary without
architecture review.

Administrative Audit Actions

The following audit actions are authoritative:

CLAIM_LOCK_POLICY_CREATE;
CLAIM_LOCK_POLICY_UPDATE;
CLAIM_LOCK_POLICY_ENABLE;
CLAIM_LOCK_POLICY_DISABLE;
CLAIM_LOCK_POLICY_ARCHIVE.

Quota audit actions must not be reused.

The target type is:

claim_lock_policy

The target identifier is:

policy_id

Successful Mutation Audit

A successful administrative mutation must use:

EnterpriseAdminAuditOutcome.SUCCEEDED

The service constructs the successful audit event before invoking the atomic
mutation repository.

Successful mutation and successful audit evidence are committed atomically.

The following state is forbidden:

policy mutation committed
successful administrative audit missing
Denied Mutation Audit

An authorization failure or denial must produce administrative audit evidence
with:

EnterpriseAdminAuditOutcome.DENIED

The policy mutation must not occur.

Denied-audit persistence uses the existing admin-audit recording service
because there is no successful policy mutation to commit atomically.

Failed Mutation Audit

A mutation that passes authorization but fails validation, lifecycle,
concurrency, or persistence must produce failed administrative evidence where
the established audit architecture permits recording that failure.

The failure audit outcome is:

EnterpriseAdminAuditOutcome.FAILED

The successful atomic audit event must never be persisted if the authoritative
mutation fails.

Audit Persistence Failure

Administrative audit evidence is authoritative.

The service must not silently continue when required audit persistence fails.

If the persistence architecture cannot guarantee required mutation-plus-audit
atomicity, the administration boundary fails as:

transaction_required

The service must fail closed.

Atomic Mutation Boundary

Successful create uses:

create_policy_with_audit(...)

Successful update, enable, disable, and archive use:

update_policy_with_audit(...)

The service must not perform a successful mutation by calling the base policy
repository and admin-audit repository independently.

The atomic mutation repository is authoritative for successful
mutation-plus-audit commit semantics.

Repository Error Mapping

The service must translate lower-level repository/domain failures into the
frozen administration vocabulary.

Required semantic mappings include:

current policy uniqueness violation -> policy_already_exists;
missing policy -> policy_not_found;
archived terminal violation -> policy_archived;
stale expected revision -> revision_conflict;
invalid canonical workspace term -> invalid_workspace_term;
mutation persistence rejection -> persistence_rejected;
incompatible transaction boundary -> transaction_required.

The service must avoid exposing persistence implementation details as public
administration semantics.

Persistence Rejection

persistence_rejected represents a mutation that cannot be accepted by the
authoritative domain/repository contract but is not more precisely represented
by another frozen failure reason.

It must not replace more specific failures such as:

policy_already_exists;
policy_archived;
revision_conflict;
invalid_workspace_term.
Transaction Required

transaction_required is used when the runtime composition cannot satisfy the
required atomic successful policy-plus-audit persistence boundary.

Examples include incompatible repository backends or different SQLite database
boundaries.

The service must not degrade to best-effort sequential persistence.

Timestamp Authority

Creation and update timestamps are server-authoritative.

Client input must not set authoritative:

created_at;
updated_at.

Create sets:

created_at;
updated_at.

Update/lifecycle mutation preserves:

created_at.

and advances:

updated_at.

All persisted timestamps must satisfy the canonical timezone-aware domain
contract.

Actor Authority

Administrative callers provide an actor user identifier.

The actor identifier is used to resolve enterprise authority.

It is not itself proof of authority.

Successful create records the actor as:

creator;
updater.

Subsequent successful mutations preserve creator identity and set the current
actor as updater.

State Preservation on Failure

Any denied or failed mutation must preserve authoritative policy state.

The following must remain unchanged on failure:

policy identifier;
workspace identifier;
policy version;
lifecycle status;
enforcement mode;
protected terms;
provenance;
revision;
creator identity;
creation timestamp;
updater identity;
update timestamp.

A failed mutation must not create a partially advanced revision.

HTTP Separation

C4 does not implement HTTP routes.

The later API layer will map the frozen administration failure reasons
according to C2.

The service must not raise FastAPI HTTPException.

The service remains framework-independent.

Frozen HTTP Mapping for Later API Work

The later API layer must preserve the existing C2 mapping:

HTTP 403
authorization_resolution_failed;
authorization_denied.
HTTP 404
policy_not_found;
policy_scope_mismatch.
HTTP 409
policy_already_exists;
policy_archived;
policy_not_active;
policy_already_active;
policy_already_disabled;
revision_conflict.
HTTP 422
invalid_workspace_term.
HTTP 500
transaction_required.

persistence_rejected remains a service failure whose exact route-level
handling must not weaken or obscure a more specific failure mapping.

No Runtime Claim Lock Composition

C4 does not:

load workspace policy during rewrite execution;
merge workspace and request terms;
resolve strongest enforcement mode;
require claim_lock.use;
build the effective runtime ClaimLock;
persist rewrite execution evidence.

Those responsibilities remain reserved for the later V2.12 runtime integration
phase.

No API Models

C4 does not authorize changes to:

apps/api/app/v2/api/models.py

Request and response models belong to the subsequent API activation phase.

No Routes

C4 does not authorize changes to:

apps/api/app/v2/api/routes.py

The frozen HTTP surface remains defined upstream, but route implementation is a
later phase.

No Dependency Wiring

C4 does not yet authorize runtime dependency-container changes unless a later
bounded implementation gate explicitly activates them.

The service may be implemented and tested through direct construction first.

Test Contract

Service-level tests must prove at minimum:

read requires claim_lock.read;
mutation requires claim_lock.manage;
authorization resolution failure fails closed;
authorization denial fails closed;
cross-workspace scope is not administratively usable;
missing current policy returns policy_not_found;
create constructs canonical revision-1 provenance;
create rejects duplicate current policy;
update reconstructs provenance for the new revision;
update preserves immutable identity/creation metadata;
stale revision maps to revision_conflict;
invalid protected term maps to invalid_workspace_term;
enable only performs disabled -> active;
enable on active returns policy_already_active;
disable only performs active -> disabled;
disable on disabled returns policy_already_disabled;
archive accepts active or disabled;
archive is terminal;
archived mutation returns policy_archived;
successful create uses CLAIM_LOCK_POLICY_CREATE;
successful PATCH uses CLAIM_LOCK_POLICY_UPDATE;
successful enable uses CLAIM_LOCK_POLICY_ENABLE;
successful disable uses CLAIM_LOCK_POLICY_DISABLE;
successful archive uses CLAIM_LOCK_POLICY_ARCHIVE;
successful mutation uses the atomic mutation boundary;
denied mutation preserves policy state;
failed mutation preserves policy state;
audit persistence failure fails closed;
incompatible atomic persistence maps to transaction_required.
Implementation Boundary

C4 implementation is authorized only for:

NEW:

apps/api/app/v2/services/enterprise_claim_lock_admin_service.py

NEW:

apps/api/tests/v2/test_enterprise_claim_lock_admin_service.py

Existing Claim Lock domain, repository, authorization, audit, API, runtime, and
frontend files are not authorized for modification by the C4 service
implementation unless an explicit architecture amendment is approved first.

Explicit Non-Goals

C4 does not authorize:

new Claim Lock permissions;
claim_lock.use runtime enforcement;
new Claim Lock validation semantics;
semantic claim enforcement;
protected-value workspace configuration;
physical policy deletion;
multi-policy public administration;
organization-global Claim Lock policy;
system-global Claim Lock policy;
policy inheritance;
regex protected terms;
wildcard protected terms;
provider-specific behavior;
frontend Claim Lock activation;
API route implementation;
rewrite-runtime integration;
rewrite-history changes;
provider routing changes;
EvalOps changes;
NEXUS changes.
C4 Freeze Disposition

The V2.12 Claim Lock administration service contract is frozen as follows:

Service: EnterpriseClaimLockAdminService
Read permission: claim_lock.read
Mutation permission: claim_lock.manage
Request runtime permission: claim_lock.use OUTSIDE C4
Read operation: get_policy
Mutations: create / update / enable / disable / archive
Workspace provenance: SERVICE-CONSTRUCTED
Provenance origin: WORKSPACE
Provenance revision: MUST MATCH NEW POLICY REVISION
Optimistic concurrency: REQUIRED
Successful mutation audit: ATOMIC
Denied/failed audit: REQUIRED
Cross-tenant isolation: FAIL CLOSED
Archived lifecycle: TERMINAL
Same-status PATCH: ALLOWED
Same-status semantic enable/disable: REJECTED
Physical delete: FORBIDDEN
HTTP framework coupling: FORBIDDEN
Runtime Claim Lock composition: OUTSIDE C4
API routes/models: OUTSIDE C4
Frontend: OUTSIDE C4

This document is the authoritative V2.12-C4 administration service design
boundary.

Implementation must not expand or weaken this contract without explicit
architecture review.
