# V2.11 Enterprise Membership Administration Release Evidence

## Release boundary

V2.11 activates governed enterprise workspace membership administration and
the Members & Roles enterprise dashboard surface.

## Release branch

```text
v2/enterprise-ui-shell
```

V2.11 extends the existing enterprise workspace authorization authority.

It does not replace or weaken:

- canonical enterprise workspace contracts;
- enterprise membership contracts;
- RBAC contracts;
- authorization resolver contracts.

## Delivered capabilities

V2.11 provides:

- workspace-scoped member listing and lookup;
- existing-user membership creation;
- governed role changes;
- suspend, reactivate, and remove lifecycle operations;
- explicit workspace ownership transfer;
- persistent SQLite membership administration;
- cross-tenant confidentiality and mutation protection;
- typed frontend membership API client;
- Members & Roles dashboard activation;
- permission-gated administrative controls;
- browser/runtime validation against the canonical persistent workspace.

## Explicit exclusions

V2.11 does not introduce:

- email invitation delivery;
- pending invitation tokens;
- invitation acceptance workflows;
- invitation expiration;
- browser-authoritative roles or permissions;
- a second membership authorization authority;
- physical deletion of removed memberships;
- OWNER assignment through normal role change.

Release evidence is prepared before staging and commit.

Commit identity is intentionally not asserted until an explicit staging and
commit phase is authorized.

---

## Canonical authority

Enterprise membership administration continues to use:

- canonical enterprise workspace authority;
- canonical enterprise membership repository;
- enterprise authorization resolver;
- backend-derived enterprise RBAC permissions.

The browser supplies:

- actor identifiers;
- target identifiers.

The browser does not establish authorization through:

- actor role;
- effective permissions;
- workspace ownership claims;
- target authorization claims.

Authorization remains server-resolved.

Legacy membership storage remains compatibility-only and is not an
authorization source.

---

# Role and lifecycle vocabulary

## Roles

```text
owner
admin
editor
reviewer
viewer
```

## Membership states

```text
active
suspended
removed
```

A removed membership remains persisted as historical membership evidence.

Removal is a lifecycle transition, not physical deletion.

---

# Permission contract

Existing enterprise permissions remain:

```text
members.read
members.invite
members.role_assign
members.remove
workspace.transfer_ownership
```

Permission mapping:

| Operation | Required permission |
| --- | --- |
| List members | `members.read` |
| Get member | `members.read` |
| Add member | `members.invite` |
| Change role | `members.role_assign` |
| Suspend member | `members.remove` |
| Reactivate member | `members.remove` |
| Remove member | `members.remove` |
| Transfer ownership | `workspace.transfer_ownership` |

No additional membership permission vocabulary was introduced.

---

## Ownership invariant

OWNER remains protected.

V2.11 preserves:

```text
member cannot be created as OWNER

normal role change cannot promote to OWNER

normal role change cannot demote current OWNER

OWNER cannot be suspended

OWNER cannot be removed

ownership changes only through ownership-transfer operation

previous OWNER -> ADMIN

target active member -> OWNER

ownership update is atomic
```

Browser validation intentionally did not mutate the canonical owner because
ownership transfer was already validated through automated service/API
persistence tests.

---

# HTTP contract

Activated endpoints:

```text
GET    /api/v2/workspaces/{workspace_id}/members
GET    /api/v2/workspaces/{workspace_id}/members/{user_id}
POST   /api/v2/workspaces/{workspace_id}/members
PATCH  /api/v2/workspaces/{workspace_id}/members/{user_id}/role
POST   /api/v2/workspaces/{workspace_id}/members/{user_id}/suspend
POST   /api/v2/workspaces/{workspace_id}/members/{user_id}/reactivate
DELETE /api/v2/workspaces/{workspace_id}/members/{user_id}
POST   /api/v2/workspaces/{workspace_id}/ownership-transfer
```

---

# Persistence contract

V2.11 uses the same persistence configuration as the enterprise authorization
runtime.

Validated persistence scenarios:

```text
membership creation
role change
suspension
reactivation
removal
removed membership history
rejoin using new membership ID
ownership transfer
```

Ownership transfer persists both role changes atomically.

---

## Cross-tenant boundary

Validated protections include:

```text
Workspace A cannot list Workspace B memberships

Workspace A cannot retrieve Workspace B membership details

Workspace A cannot add membership to Workspace B

Workspace A cannot change Workspace B role

Workspace A cannot suspend Workspace B member

Workspace A cannot remove Workspace B member

Workspace A cannot transfer Workspace B ownership
```

Foreign and nonexistent targets return equivalent externally visible behavior
where confidentiality requires it.

---

# Frontend API contract

Typed membership client:

```text
apps/web/src/api/members.ts
```

Supported operations:

```text
member list
member lookup
membership creation
role change
suspension
reactivation
removal
ownership transfer
```

Frontend conventions preserved:

- native fetch;
- encoded identifiers;
- URLSearchParams;
- JSON request bodies;
- bounded backend error propagation;
- response validation.

OWNER is not exposed as an ordinary role selection.

---

# Members & Roles dashboard activation

Route:

```text
#/members
```

V2.11 changes the Members route from reserved/planned to available.

Validated:

- route loads;
- workspace context resolves;
- member inventory renders from API;
- backend permissions drive actions;
- OWNER protections remain visible;
- ownership transfer visibility is permission controlled.

---

# Automated validation evidence

## M3 — Membership HTTP API

Completed.

## M4-A — SQLite persistence/restart

```text
5 passed, 1 known warning
```

## M4-B — Lifecycle failure semantics

```text
9 passed, 1 known warning
```

Combined M3 + M4:

```text
54 passed, 1 known warning
```

## M5 — Cross-tenant regression

```text
9 passed, 1 known warning
```

Combined M3 + M4 + M5:

```text
63 passed, 1 known warning
```

## M6 — Frontend validation

```text
npx tsc --noEmit
PASS

npm run build
PASS
```

## M7 — Members & Roles activation

Completed.

## M8 — Browser/runtime validation

Completed.

---

## Browser/runtime evidence

Canonical persistent workspace:

```text
workspace_e6c41dc7f2a244d99af87168a80033f6
```

Canonical owner:

```text
user_7b0e47e95d6b47f6a03c55d81b2b6a6a
```

Validated:

```text
Members route loads

workspace context resolves

owner renders correctly

permissions resolve from backend

member inventory renders from API

reload preserves persisted state

membership requests complete successfully
```

---

# Scope preservation

V2.11 does not activate:

```text
Claim Lock workspace administration
EvalOps
Providers
Routing
Policies
Settings
```

Those remain governed by existing planned/release boundaries.

---

# Current implementation boundary

V2.11 changes only:

```text
apps/api/app/v2/api/dependencies.py
apps/api/app/v2/api/models.py
apps/api/app/v2/api/routes.py
apps/api/tests/v2/test_enterprise_membership_admin_api.py
apps/api/tests/v2/test_enterprise_membership_admin_api_persistence.py
apps/api/tests/v2/test_enterprise_membership_admin_cross_tenant_api.py
apps/web/src/api/members.ts
apps/web/src/app/navigation.ts
apps/web/src/pages/MembersPage.tsx
apps/web/src/App.tsx
```

SQLite runtime database remains ignored and is not a release artifact.

FETCH_HEAD is unrelated local repository state.

---

## Final release gate

V2.11 final regression validation completed successfully.

Targeted membership regression:

```text
63 passed, 1 warning in 2.52s

The warning is the existing Starlette/TestClient httpx deprecation warning
and is unrelated to V2.11 membership administration.

Full API regression:

2198 passed, 1 warning in 19.75s

The full API suite was executed from the canonical API project directory:

apps/api

This was required because an existing provider-quality test resolves
app/providers/cloudflare.py relative to the API project working directory.

A repository-root invocation produced a path-resolution failure in that
existing test. No source changes were required. Re-running from the API
project directory produced the complete passing result above.

Frontend TypeScript validation:

npx tsc --noEmit
PASS

Frontend production build:

vite v7.3.6
54 modules transformed
PASS

Diff hygiene:

git diff --check
PASS

Final working-tree inspection:

implementation files only
release evidence file only
FETCH_HEAD untouched

No staging, commit, push, or pull request occurred during M9 validation.

# Release status

```text
M1 — Contract inventory                         COMPLETE
M2 — Membership HTTP API design                COMPLETE
M3 — Membership HTTP API                       COMPLETE
M4 — Persistence/Lifecycle HTTP Validation     COMPLETE
M5 — Cross-Tenant HTTP Regression              COMPLETE
M6 — Frontend API Client                       COMPLETE
M7 — Members & Roles Page Activation           COMPLETE
M8 — Browser/runtime validation                 COMPLETE
M9 — Release evidence                          IN PROGRESS
```

No staging, commit, push, or pull request is authorized by this release
evidence document.
