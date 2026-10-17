# Humanize V3.6 — Approval State Machine R1

## State set

`PENDING`
- valid request;
- valid policy;
- no terminal negative decision;
- authorized approvals are below threshold.

`APPROVED`
- valid request;
- valid policy;
- no reject or revision decision;
- unique authorized approvals meet or exceed threshold.

`REJECTED`
- at least one authorized required approver explicitly rejects;
- terminal for this approval request identity.

`REVISION_REQUIRED`
- at least one authorized required approver explicitly requires revision;
- terminal for this approval request identity.

`ERROR`
- structural invalidity;
- V3.5 `BLOCK` or `ERROR` input;
- cross-tenant or cross-engagement evidence;
- stale request/composition mismatch;
- invalid authority binding;
- unknown approver;
- conflicting decisions from one approver;
- invalid policy;
- malformed identity/hash;
- any other fail-closed contradiction.

## Precedence

Evaluation precedence is exact:

1. structural request invalidity -> `ERROR`
2. structural policy invalidity -> `ERROR`
3. source disposition `ERROR` -> `ERROR`
4. source disposition `BLOCK` -> `ERROR`
5. tenant/engagement mismatch -> `ERROR`
6. request/composition identity mismatch or staleness -> `ERROR`
7. authority binding invalidity -> `ERROR`
8. unknown approver or unauthorized decision -> `ERROR`
9. conflicting decisions by the same approver -> `ERROR`
10. authorized `REJECT` present -> `REJECTED`
11. authorized `REQUIRE_REVISION` present -> `REVISION_REQUIRED`
12. approval threshold satisfied -> `APPROVED`
13. otherwise -> `PENDING`

## Transition semantics

The service is a deterministic evaluator, not a mutable workflow engine. State is derived from the immutable request, policy, authority bindings, and complete decision set supplied to the call.

Permitted derived progression:
- `PENDING` -> `APPROVED`
- `PENDING` -> `REJECTED`
- `PENDING` -> `REVISION_REQUIRED`
- any valid evaluation -> `ERROR` when contradictory or invalid evidence is supplied

A terminal result does not authorize mutation of historical evidence.

## Revision semantics

`REVISION_REQUIRED` never edits the V3.5 composition. The composition must be revised by the appropriate upstream capability, producing a new V3.5 composition identity. The new composition requires a new approval request.

## Staleness

An approval request is stale for successor use when any bound V3.5 identity field differs from the composition presented for evaluation. Stale approval evidence is not silently rebound.

## Duplicate evidence

Identical duplicate decision records are idempotent and collapse to one normalized decision identity. Non-identical decisions from the same approver for the same request are conflicting and yield `ERROR`.

## Presentation-only input

`PRESENTATION_ONLY` may reach `APPROVED` as a human-review state, but the result must continue to carry `source_disposition=PRESENTATION_ONLY`. No downstream component may interpret that approval as provenance promotion or protected-fact authorization.

## No implicit success

Empty decision set, insufficient approvals, omitted human evidence, or missing required approvers never produces `APPROVED`.
