# Humanize V3.6 — Human Approval Lifecycle Architecture R1

## Status

Detached architecture candidate only. This document does not mutate the repository and does not grant implementation, validation, staging, commit, push, PR, merge, export, rendering, or delivery authority.

## Purpose

V3.6 introduces a deterministic, provider-free Human Approval Lifecycle over exact V3.5 Governed Composition outputs. The approval layer is a sidecar authority record bound to an immutable V3.5 composition identity. It does not rewrite, reparse, reclassify, or regenerate V3.5 content.

## Architectural boundary

Inputs:
- exact V3.5 composition identity and composition hash;
- V3.5 tenant and engagement identity;
- V3.5 disposition and authority/provenance trace;
- an immutable approval policy binding;
- explicit human decision evidence;
- explicit approver authority bindings.

Outputs:
- approval request identity;
- deterministic approval state;
- immutable decision records and decision identities;
- approval evidence/audit trace;
- fail-closed error/block reasons where applicable.

Explicitly excluded:
- delivery manifest construction;
- export authorization;
- DOCX/PDF/PPTX rendering;
- client handoff packaging;
- provider IAM lookup;
- network calls;
- persistence;
- mutable clock reads;
- randomness;
- background jobs;
- V3.5 provenance or classification mutation.

## Core invariants

1. V3.5 composition identity is immutable input authority.
2. Approval is an overlay decision, never a rewrite of V3.5 composition content.
3. A V3.5 `BLOCK` or `ERROR` disposition can never become authoritative because a human approved it.
4. `PRESENTATION_ONLY` remains presentation-only even when approved; approval does not promote it to a protected fact.
5. Approval scope is tenant- and engagement-bound.
6. No implicit approval exists. Missing or insufficient decision evidence remains `PENDING`.
7. A decision is bound to one exact approval request and therefore one exact V3.5 composition identity.
8. A composition change requires a new approval request identity. Prior approval may remain historical evidence but is stale for the changed composition.
9. Decision ordering and aggregation are deterministic.
10. Invalid, conflicting, unauthorized, stale, cross-tenant, or cross-engagement evidence fails closed.
11. Core semantics depend on no system clock, network, provider, filesystem state, database state, randomness, or process-local mutable state.
12. V3.6 authorizes only approval lifecycle semantics. Successor delivery/export authority belongs to V3.7 or later.

## Proposed provider-free namespace

`app.v3.approval`

Proposed modules for later implementation planning:
- `contracts.py`
- `identity.py`
- `authority.py`
- `ordering.py`
- `state.py`
- `service.py`
- `__init__.py`

No repository path is authorized by this detached candidate. Any repository materialization pathset requires a later, separately accepted scope review.

## Approval model

A request binds:
- `tenant_id`
- `engagement_id`
- `composition_id`
- `composition_hash`
- `composition_disposition`
- `approval_policy_id`
- `approval_policy_hash`
- `requested_scope`

A decision binds:
- `approval_request_id`
- `approver_id`
- `approver_authority_hash`
- `decision`
- `reason_code`
- `evidence_hash`

The service derives an aggregate approval state only from exact bound inputs.

## Allowed aggregate states

- `PENDING`
- `APPROVED`
- `REJECTED`
- `REVISION_REQUIRED`
- `ERROR`

`APPROVED` means only that the exact V3.5 composition has satisfied the V3.6 human-approval policy. It does not mean exported, delivered, published, rendered, or otherwise operationalized.

## Terminality and revision

`REJECTED` and `REVISION_REQUIRED` are terminal for a given approval request identity. A revised composition must obtain a new V3.5 composition identity and therefore a new V3.6 approval request. V3.6 never mutates a completed request into a request for different content.

## Determinism

Canonical serialization and SHA-256 identity are used only for identity and evidence binding. They do not create new truth authority. Equivalent input sets must yield byte-identical normalized decision ordering, request identity, decision identities, aggregate state, and approval trace.

## Successor boundary

Only a separately authorized V3.7 capability may interpret an `APPROVED` V3.6 result together with the preserved V3.5 disposition for delivery-manifest or export-authorization purposes.
