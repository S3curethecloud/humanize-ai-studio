# Enterprise Claim Lock Domain and Repository Contract V2.12

## Status

This document freezes the V2.12-C3 domain and repository contract for
Enterprise Workspace Claim Lock governance.

It implements the architectural direction established by:

`docs/architecture/ENTERPRISE_CLAIM_LOCK_GOVERNANCE_V2_12.md`

This document does not authorize API routes, runtime rewrite integration,
frontend activation, or Claim Lock validator changes.

## C3 Scope

V2.12-C3 defines only:

- the canonical workspace Claim Lock policy domain model;
- lifecycle state representation;
- domain validation;
- protected-term provenance requirements;
- repository protocol;
- in-memory repository behavior;
- SQLite repository behavior;
- workspace cardinality;
- optimistic concurrency;
- atomic policy-plus-audit persistence;
- lifecycle transition persistence;
- persistence integrity;
- required domain and repository test coverage.

## Existing Contracts To Reuse

C3 must reuse existing Claim Lock primitives.

The following existing types remain authoritative:

- `ClaimLockEnforcementMode`;
- `ClaimLockOrigin`;
- `ClaimLockProvenance`;
- `ProtectedTerm`.

C3 must not introduce parallel workspace-specific versions of these types.

The existing Claim Lock validator remains unchanged.

The existing runtime `ClaimLock` model remains unchanged.

## Canonical Domain File

The bounded implementation file is:

`apps/api/app/v2/domain/enterprise_claim_lock_policy.py`

The domain contract version is:

`enterprise-workspace-claim-lock-policy-v1`

The implementation must expose a constant equivalent to:

`ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION`

## Policy Lifecycle Enum

The domain must define:

`EnterpriseClaimLockPolicyStatus`

with exactly these values:

- `active`;
- `disabled`;
- `archived`.

No additional lifecycle state is authorized in C3.

## Canonical Policy Model

The domain must define:

`EnterpriseWorkspaceClaimLockPolicy`

The model must be immutable and must reject unknown fields.

The policy fields are:

- `policy_version`;
- `policy_id`;
- `workspace_id`;
- `status`;
- `enforcement_mode`;
- `protected_terms`;
- `created_by_user_id`;
- `created_at`;
- `updated_by_user_id`;
- `updated_at`;
- `revision`.

The canonical policy version is:

`enterprise-workspace-claim-lock-policy-v1`

## Domain Model Shape

Conceptually:

```python
class EnterpriseWorkspaceClaimLockPolicy(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    policy_version: Literal[
        "enterprise-workspace-claim-lock-policy-v1"
    ] = ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION

    policy_id: str
    workspace_id: str

    status: EnterpriseClaimLockPolicyStatus
    enforcement_mode: ClaimLockEnforcementMode

    protected_terms: tuple[ProtectedTerm, ...]

    created_by_user_id: str
    created_at: datetime

    updated_by_user_id: str
    updated_at: datetime

    revision: int
```

The implementation may apply bounded field-length constraints consistent with
existing enterprise domain models.

## Domain Invariants

The domain must enforce:

- `policy_id` is non-empty;
- `workspace_id` is non-empty;
- `created_by_user_id` is non-empty;
- `updated_by_user_id` is non-empty;
- `created_at` is timezone-aware;
- `updated_at` is timezone-aware;
- `updated_at >= created_at`;
- `revision >= 1`;
- every protected term has workspace provenance;
- every protected term references the current policy revision;
- duplicate protected-term identifiers are forbidden case-insensitively;
- duplicate protected-term semantic content is forbidden;
- unknown fields are forbidden;
- policy instances are immutable.

## Protected Workspace Terms

Workspace policy protected terms must reuse canonical `ProtectedTerm`.

Every persisted workspace-protected term must have:

`provenance.origin = ClaimLockOrigin.WORKSPACE`

The required provenance source reference is:

`workspace-claim-lock-policy:<policy_id>:revision:<revision>`

A persisted policy revision must not contain workspace terms referencing another
policy identifier or another revision.

Client-supplied provenance is not authoritative.

## Empty Protected-Term Set

The workspace policy domain allows:

`protected_terms = ()`

The policy object is administration configuration and is not itself a runtime
`ClaimLock`.

Therefore the runtime `ClaimLock` requirement to protect at least one item does
not apply directly to the workspace policy object.

Runtime composition remains responsible for determining whether an effective
runtime `ClaimLock` is constructed.

## Duplicate Term Rules

Within one policy revision:

- duplicate term identifiers are rejected case-insensitively;
- duplicate term semantic content is rejected;
- duplicate semantic comparison follows existing protected-term case-folded
  semantics.

Persistence must not silently merge duplicate terms.

## Policy Revision Contract

A newly created policy starts at:

`revision = 1`

Every successful mutation after creation increments revision exactly once.

The following operations increment revision exactly once:

- PATCH/update;
- enable;
- disable;
- archive.

A failed mutation does not increment revision.

An authorization denial does not increment revision.

A revision conflict does not increment revision.

An atomic audit failure does not leave a visible incremented revision.

## Revision Lineage

Revision numbers belong to one policy identifier.

Example:

```text
policy_001
revision 1
revision 2
revision 3
revision 4
```

If `policy_001` becomes archived, its lineage is terminal.

A later new policy uses a new policy identifier and starts again at revision 1.

Example:

```text
policy_002
revision 1
```

Revision numbers do not continue across policy identifiers.

## Lifecycle Semantics

### Active

An active policy is the current authoritative workspace policy and may
contribute mandatory runtime protection.

### Disabled

A disabled policy is still the current authoritative workspace policy but does
not contribute runtime workspace protection.

A disabled policy may later transition back to active.

### Archived

An archived policy is historical and terminal.

An archived policy:

- cannot be reactivated;
- cannot be disabled;
- cannot be edited;
- cannot be physically deleted;
- remains retrievable by policy identifier;
- remains auditable;
- is excluded from current workspace policy resolution.

## Archival and Workspace Cardinality

Archival is terminal for the specific policy object, not for the workspace.

A workspace may have:

- zero or one non-archived policy;
- zero or more archived historical policies.

After the current policy is archived, the workspace may create a brand-new
policy with a new `policy_id`.

The new policy starts at revision 1.

This rule preserves historical policy lineage without permanently preventing
future Claim Lock governance for the workspace.

## Allowed Lifecycle Transitions

The persistence contract allows:

| Current state | Requested state | Allowed |
| --- | --- | --- |
| none | active | yes |
| none | disabled | yes |
| none | archived | no |
| active | active | no |
| active | disabled | yes |
| active | archived | yes |
| disabled | active | yes |
| disabled | disabled | no |
| disabled | archived | yes |
| archived | active | no |
| archived | disabled | no |
| archived | archived | no |

Direct creation of an archived policy is forbidden.

## Repository File

The bounded repository implementation file is:

`apps/api/app/v2/repositories/enterprise_claim_lock_policies.py`

The file must define:

- repository protocol;
- in-memory implementation;
- SQLite implementation;
- repository-specific integrity helpers as required.

## Repository Protocol

The canonical protocol is conceptually:

```python
class EnterpriseWorkspaceClaimLockPolicyRepository(Protocol):
    def create(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        ...

    def get_by_id(
        self,
        policy_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        ...

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        ...

    def update(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        ...
```

C3 does not authorize:

- physical delete;
- unrestricted list-all;
- blind replace;
- upsert;
- update without expected revision.

## Repository Authorization Boundary

The repository contains no enterprise authorization logic.

Authorization belongs in the later administration service layer.

The repository accepts already-authorized domain operations and enforces
persistence integrity only.

## Create Contract

`create()` must reject creation when:

- `policy_id` already exists;
- the workspace already has a non-archived policy;
- policy revision is not 1;
- lifecycle status is archived;
- policy domain validation fails.

Creation must never silently replace existing state.

Creation is not an upsert.

## Current Workspace Resolution

`get_for_workspace(workspace_id)` resolves the current non-archived policy.

Result contract:

```text
zero matching non-archived policies -> None
one matching non-archived policy     -> return policy
more than one                        -> persistence integrity failure
```

The repository must not arbitrarily choose between conflicting current
policies.

Archived historical policies are excluded from this lookup.

## Historical Lookup

`get_by_id(policy_id)` may return:

- active policy;
- disabled policy;
- archived policy;
- `None`.

Archived policies remain addressable by policy identifier for historical and
audit purposes.

## Update Contract

`update()` uses optimistic concurrency.

The stored revision must equal:

`expected_revision`

Otherwise the repository raises a revision-conflict error.

The candidate policy must satisfy:

- same `policy_id`;
- same `workspace_id`;
- same `policy_version`;
- same `created_by_user_id`;
- same `created_at`;
- candidate revision equals `expected_revision + 1`.

The following fields are immutable across revisions:

- `policy_version`;
- `policy_id`;
- `workspace_id`;
- `created_by_user_id`;
- `created_at`.

The following fields may change subject to lifecycle rules:

- `status`;
- `enforcement_mode`;
- `protected_terms`;
- `updated_by_user_id`;
- `updated_at`;
- `revision`.

Archived policies cannot be updated.

## Repository Failure Boundary

The persistence layer must use repository-level errors and must not depend on
HTTP response concepts.

Conceptual repository errors include:

- `EnterpriseClaimLockPolicyAlreadyExistsError`;
- `EnterpriseClaimLockPolicyRevisionConflictError`;
- `EnterpriseClaimLockPolicyIntegrityError`;
- `EnterpriseClaimLockPolicyNotFoundError`;
- `EnterpriseClaimLockPolicyArchivedError`.

The later service/API layer maps repository failures into the frozen V2.12
administration failure vocabulary.

## In-Memory Repository

The in-memory implementation must use:

- `RLock`;
- immutable policy objects;
- copy-on-write authoritative state replacement.

Stored policy objects must not be mutated in place.

Concurrent readers must not observe partially replaced policy state.

## SQLite Repository

The SQLite implementation must persist workspace policy state in a dedicated
table.

The conceptual table is:

```sql
CREATE TABLE IF NOT EXISTS
enterprise_workspace_claim_lock_policies (
    policy_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL,
    enforcement_mode TEXT NOT NULL,
    revision INTEGER NOT NULL,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_by_user_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
```

The canonical serialized immutable policy remains persisted in `payload`.

Queryable authority fields are also stored as dedicated columns for integrity
and lookup.

## SQLite Current-Policy Integrity

SQLite must enforce at most one non-archived policy per workspace.

Conceptually:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS
uq_enterprise_claim_lock_policy_current_workspace
ON enterprise_workspace_claim_lock_policies (
    workspace_id
)
WHERE status != 'archived';
```

This permits historical archived policies while preventing multiple active or
disabled current policies for one workspace.

## SQLite Lookup Index

SQLite may define a supporting index equivalent to:

```sql
CREATE INDEX IF NOT EXISTS
idx_enterprise_claim_lock_policy_workspace
ON enterprise_workspace_claim_lock_policies (
    workspace_id,
    status,
    policy_id
);
```

Indexes must not weaken the unique current-policy constraint.

## SQLite Timestamp Contract

All domain timestamps must be timezone-aware.

SQLite serialization normalizes persisted timestamps to UTC ISO-8601.

Timezone-naive persistence is forbidden.

## SQLite Update Transaction

SQLite updates must use a write transaction equivalent to:

`BEGIN IMMEDIATE`

Within the transaction the repository must validate:

- policy exists;
- policy is not archived;
- stored revision equals expected revision;
- candidate identity matches stored identity;
- candidate revision equals expected revision plus one;
- lifecycle transition is permitted;
- workspace cardinality remains valid.

The final update must be revision guarded.

Conceptually:

```sql
UPDATE ...
SET ...
WHERE policy_id = ?
  AND revision = ?
```

Exactly one row must be affected.

Any other result is a concurrency or persistence-integrity failure.

The transaction commits only after all checks and persistence operations
succeed.

Otherwise it rolls back.

## Enterprise Admin Audit Action Extension

C3 implementation requires a bounded extension to the existing enterprise
admin-audit action enum.

The existing file authorized for modification is:

`apps/api/app/v2/domain/enterprise_admin_audit.py`

The existing `EnterpriseAdminAuditEvent` model and enterprise admin-audit
repository architecture remain authoritative and must not be redesigned for
Claim Lock.

C3 authorizes exactly these additional `EnterpriseAdminAuditAction` values:

```python
CLAIM_LOCK_POLICY_CREATE = "claim_lock_policy_create"
CLAIM_LOCK_POLICY_UPDATE = "claim_lock_policy_update"
CLAIM_LOCK_POLICY_ENABLE = "claim_lock_policy_enable"
CLAIM_LOCK_POLICY_DISABLE = "claim_lock_policy_disable"
CLAIM_LOCK_POLICY_ARCHIVE = "claim_lock_policy_archive"
```

No additional Claim Lock policy audit action is authorized in C3.

Quota audit actions must not be reused for Claim Lock operations.

The following existing audit contracts remain unchanged:

- `EnterpriseAdminAuditEvent`;
- `EnterpriseAdminAuditOutcome`;
- admin-audit target type and target identifier semantics;
- admin-audit timestamp semantics;
- admin-audit failure-reason semantics;
- in-memory admin-audit repository behavior;
- SQLite admin-audit repository behavior.

## Atomic Administration Mutation File

The bounded atomic mutation implementation file is:

`apps/api/app/v2/repositories/enterprise_claim_lock_policy_admin_mutations.py`

It must be separate from the base policy repository.

## Atomic Mutation Protocol

Conceptually:

```python
class EnterpriseClaimLockPolicyAdminMutationRepository(Protocol):
    def create_policy_with_audit(...):
        ...

    def update_policy_with_audit(...):
        ...
```

Enable, disable, and archive are persisted through the update mutation
primitive.

Their distinct administrative meaning is carried by the audit action and
service-layer operation.

## Atomic SQLite Requirement

For SQLite, the policy repository and enterprise admin-audit repository must use
the same SQLite database.

If atomic mutation cannot be guaranteed because they use incompatible
persistence boundaries, configuration must fail rather than degrade to
best-effort behavior.

This condition maps later to the frozen administration failure:

`transaction_required`

## Atomic SQLite Mutation

A successful administrative mutation follows the conceptual sequence:

```text
BEGIN IMMEDIATE

validate policy mutation
persist policy
persist successful admin audit event

COMMIT
```

Any failure must cause:

`ROLLBACK`

The following state is forbidden:

```text
policy mutation persisted
successful audit evidence missing
```

## Atomic In-Memory Mutation

The in-memory atomic mutation repository must use a fixed lock order.

Required lock order:

1. policy authority;
2. admin audit evidence.

Both locks remain held while candidate authoritative copies are validated and
replaced.

Readers must not observe a partial successful mutation.

## Audit Coupling Boundary

C3 defines persistence atomicity only.

C3 does not yet define the full administration service.

The later administration service will determine:

- required enterprise permission;
- audit action;
- audit outcome;
- target type;
- target identifier;
- failure mapping.

C3 only guarantees that successful authoritative mutation and successful audit
evidence cannot diverge.

## Protected-Term Mutation Boundary

The persisted domain policy must contain canonical workspace provenance.

Client/API input must not be treated as authoritative provenance.

The later administration layer may accept term configuration fields such as:

- `term_id`;
- `text`;
- `case_sensitive`.

It must construct canonical `ProtectedTerm` instances using:

`ClaimLockOrigin.WORKSPACE`

and:

`workspace-claim-lock-policy:<policy_id>:revision:<new_revision>`

before persistence.

## Concurrency Contract

Optimistic concurrency is mandatory.

For two concurrent updates that both expect revision `N`:

- exactly one may succeed;
- one must fail with revision conflict;
- final persisted revision must be `N + 1`;
- no mixed fields from both candidates may appear;
- successful audit evidence must correspond only to the winning mutation.

## Required Domain Tests

The C3 domain test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_policy_domain.py`

Required coverage includes:

- valid active policy;
- valid disabled policy;
- archived model representation;
- revision zero rejected;
- timezone-naive `created_at` rejected;
- timezone-naive `updated_at` rejected;
- `updated_at < created_at` rejected;
- non-workspace protected-term provenance rejected;
- wrong policy identifier in source reference rejected;
- wrong revision in source reference rejected;
- duplicate term IDs rejected case-insensitively;
- duplicate semantic term text rejected;
- empty protected-term tuple accepted;
- model immutability;
- unknown fields rejected.

## Required Repository Tests

The C3 repository test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_policy_repositories.py`

Equivalent behavioral coverage must run against:

- in-memory policy repository;
- SQLite policy repository.

Required coverage includes:

- create revision 1;
- create active;
- create disabled;
- create archived rejected;
- get by identifier;
- get current policy for workspace;
- duplicate policy ID rejected;
- second non-archived policy for workspace rejected;
- archived historical policy remains retrievable by ID;
- archived policy excluded from current workspace resolution;
- new policy allowed after archival;
- successful update;
- stale expected revision rejected;
- revision jump rejected;
- immutable identity change rejected;
- archived policy update rejected;
- lifecycle transition matrix;
- absence of physical delete contract;
- SQLite restart persistence.

## Required Atomic Mutation Tests

The C3 atomic mutation test file is:

`apps/api/tests/v2/test_enterprise_claim_lock_policy_admin_mutations.py`

Required coverage includes:

- policy create and audit both persist;
- policy update and audit both persist;
- policy persistence failure produces no successful audit mutation;
- audit persistence failure rolls back policy mutation;
- revision conflict mutates neither authority nor audit evidence;
- duplicate audit identifier mutates neither authority nor audit evidence;
- incompatible SQLite database boundaries rejected;
- in-memory atomic replacement does not expose partial success;
- SQLite atomic mutation survives restart.

## Required Concurrency Test

SQLite must include a race test where two mutations both expect the same
revision.

Acceptance criteria:

1. exactly one succeeds;
2. exactly one revision conflict occurs;
3. final revision == original revision + 1;
4. final policy fields come entirely from the winner;
5. successful audit evidence exists only for the winner.

This test is mandatory.

## C3 Implementation File Boundary

When C3 implementation is later authorized, the bounded implementation slice is:

```text
EXISTING FILE AUTHORIZED FOR BOUNDED MODIFICATION:
apps/api/app/v2/domain/enterprise_admin_audit.py

NEW DOMAIN FILE:
apps/api/app/v2/domain/enterprise_claim_lock_policy.py

NEW REPOSITORY FILES:
apps/api/app/v2/repositories/enterprise_claim_lock_policies.py
apps/api/app/v2/repositories/enterprise_claim_lock_policy_admin_mutations.py

NEW TEST FILES:
apps/api/tests/v2/test_enterprise_claim_lock_policy_domain.py
apps/api/tests/v2/test_enterprise_claim_lock_policy_repositories.py
apps/api/tests/v2/test_enterprise_claim_lock_policy_admin_mutations.py
```

The modification to
`apps/api/app/v2/domain/enterprise_admin_audit.py`
is restricted to adding the five frozen Claim Lock policy audit actions.

C3 does not authorize redesign of the existing enterprise admin-audit event or
repository contracts.

C3 does not authorize changes to:

- `apps/api/app/v2/api/routes.py`;
- `apps/api/app/v2/api/models.py`;
- `apps/api/app/v2/services/workspace_rewrite_service.py`;
- `apps/api/app/v2/domain/claim_lock.py`;
- `apps/api/app/v2/services/claim_lock_validator.py`;
- frontend files;
- navigation;
- Claim Lock page;
- runtime workspace-policy composition.

## C3 Freeze Disposition

The V2.12-C3 domain and repository contract is frozen as follows:

- Canonical policy model: REQUIRED
- Policy version: `enterprise-workspace-claim-lock-policy-v1`
- Reuse `ProtectedTerm`: REQUIRED
- Reuse `ClaimLockEnforcementMode`: REQUIRED
- Workspace provenance: REQUIRED
- Empty protected-term set: ALLOWED
- Initial revision: 1
- Successful mutation revision: +1 EXACTLY
- Active creation: ALLOWED
- Disabled creation: ALLOWED
- Archived creation: FORBIDDEN
- Archived lifecycle: TERMINAL
- Archived history: RETAINED
- New policy after archival: ALLOWED
- New policy identifier after archival: REQUIRED
- New policy revision after archival: 1
- One non-archived policy per workspace: REQUIRED
- Database enforcement of current-policy cardinality: REQUIRED
- Repository architecture: PROTOCOL + MEMORY + SQLITE
- Optimistic concurrency: REQUIRED
- SQLite mutation transaction: `BEGIN IMMEDIATE`
- Atomic policy plus successful audit: REQUIRED
- Separate atomic mutation repository: REQUIRED
- Claim Lock enterprise admin-audit actions: REQUIRED
- Authorized existing audit-domain modification: apps/api/app/v2/domain/enterprise_admin_audit.py
- Frozen Claim Lock policy audit actions: CREATE / UPDATE / ENABLE / DISABLE / ARCHIVE
- Enterprise admin-audit event redesign: FORBIDDEN
- Enterprise admin-audit repository redesign: FORBIDDEN
- Physical deletion: FORBIDDEN
- Repository HTTP coupling: FORBIDDEN
- UTC-normalized SQLite timestamps: REQUIRED
- SQLite restart persistence: REQUIRED
- Concurrent revision race test: REQUIRED

This document is the authoritative V2.12-C3 design boundary.

Implementation must remain within this domain and persistence boundary until a
later phase explicitly authorizes administration services, HTTP APIs, runtime
composition, or frontend activation.
