# HUMANIZE V3.5 — Composition Acceptance and Adversarial Criteria R1

Status: DETACHED PLANNING CANDIDATE — NOT CANONICAL — NO TEST EXECUTION AUTHORITY

## 1. Acceptance objective

Before V3.5 implementation may be accepted, tests must prove that Governed Composition is deterministic, authority-preserving, provenance-preserving, classification-safe, tenant-isolated, and fail-closed.

This document defines architecture-level criteria only. It does not authorize test execution.

## 2. Contract acceptance criteria

The implementation must expose immutable typed contracts for:

- `CompositionInput`
- `CompositionRequest`
- `GovernedCompositionEntry`
- `GovernedComposition`
- `CompositionDecision`
- deterministic evidence records

Acceptance requires that prohibited override fields do not exist for:

- truth
- provenance
- Claim Lock result
- tenant
- engagement
- classification downgrade
- protected-fact promotion

## 3. Determinism criteria

Given byte-for-byte equivalent authorized inputs and the same explicit positions:

- composition disposition must be identical.
- ordered entries must be identical.
- evidence surface must be identical.
- `composition_id` must be identical.

Given the same entries with different explicit positions:

- ordered entries must reflect the declared positions.
- `composition_id` may differ.
- no semantic reordering may occur.

Repeated execution must not depend on wall-clock time, randomness, provider calls, mutable global state, filesystem state, or network state.

## 4. Authority preservation criteria

Prove that:

- V3.4 `ELIGIBLE` protected facts remain protected-fact references.
- V3.4 `PRESENTATION_ONLY` derivations never become protected facts.
- V3.4 `BLOCK` input prevents authoritative composition.
- V3.4 `ERROR` input prevents authoritative composition.
- Claim Lock outcomes are preserved rather than recalculated.
- NDEB is not reparsed or revalidated.
- no new truth authority exists in V3.5.

## 5. Provenance criteria

For every successful composition:

- every input source reference is present in the provenance ledger.
- every source authority binding is traceable.
- every protected-fact identity is traceable.
- every presentation derivation identity is traceable.
- no synthetic provenance replaces original provenance.
- composition identity is clearly distinguished from provenance.

## 6. Classification criteria

Required cases:

1. one authoritative classification across all protected facts -> exact inheritance.
2. requested classification absent -> exact inheritance.
3. requested classification equal -> allowed.
4. requested classification unequal -> `BLOCK`.
5. two authoritative protected facts with unequal classifications -> `BLOCK`.
6. presentation derivation with a different classification must not cause downgrade or silent merge.
7. no "highest wins", "lowest wins", or inferred taxonomy behavior.

## 7. Tenant and engagement isolation criteria

Adversarial cases must prove:

- same tenant + same engagement -> potentially composable.
- different tenant -> `BLOCK`.
- different engagement -> `BLOCK`.
- mixed tenant set with one matching majority -> still `BLOCK`.
- duplicated source with altered tenant field -> `BLOCK`.
- presentation-only input from another tenant -> `BLOCK`.
- malformed missing tenant/engagement -> `ERROR`.

## 8. Protected-fact conflict criteria

Cases:

- exact same protected-fact identity and exact same bindings -> deterministic exact-duplicate evidence; no invented fact.
- same protected-fact binding key with different value identity -> `BLOCK`.
- same binding key with different provenance -> `BLOCK`.
- same binding key with different source authority -> `BLOCK`.
- same binding key with different classification -> `BLOCK`.
- multiple nonconflicting protected facts -> deterministic composition.

No test may accept last-write-wins, first-write-wins, majority vote, model arbitration, or implicit precedence.

## 9. Presentation-boundary criteria

Prove that:

- all-presentation inputs yield `PRESENTATION_ONLY`.
- mixed protected/presentation inputs preserve two distinguishable lanes.
- presentation content cannot overwrite protected fact content.
- a presentation derivation that textually resembles a protected fact remains presentation-only.
- free-form narrative cannot create a protected-fact identity.
- later rendering concerns do not enter V3.5 contracts.

## 10. Ordering adversarial criteria

Prove:

- duplicate positions -> `ERROR`.
- missing required position -> `ERROR`.
- negative positions, if disallowed by contract -> deterministic `ERROR`.
- stable ascending position ordering.
- caller list order does not override explicit position.
- no locale-dependent or hash-map-dependent ordering.
- no model-generated ordering.

## 11. Structural malformed-input criteria

Prove fail-closed behavior for:

- unknown content kind
- missing authority disposition
- missing provenance binding
- missing source authority binding
- malformed protected-fact reference
- malformed presentation-derivation reference
- mismatched request/input tenant
- mismatched request/input engagement
- duplicate input identifier

Malformed structures must never produce an authoritative composition envelope.

## 12. Composition identity criteria

Prove that the identity surface includes all fields necessary to distinguish:

- tenant
- engagement
- purpose
- explicit ordering
- entry identities
- classification
- source authority bindings
- provenance bindings
- protected-fact/presentation references

Prove that changes to any identity-bearing field change `composition_id`.

Prove explicitly that a valid hash does not upgrade `BLOCK`, `ERROR`, or `PRESENTATION_ONLY` content.

## 13. Side-effect criteria

The V3.5 core must be provider-free and pure.

Tests must prove no:

- network access
- provider mutation
- database mutation
- filesystem persistence
- renderer invocation
- approval workflow invocation
- export authorization
- delivery-format generation

## 14. Regression criteria

The accepted V3.4 authority suite must remain green after V3.5 implementation. V3.5 tests must not weaken or replace V3.4 tests.

Expected future validation layers, subject to separate authorization:

- focused V3.5 unit tests
- V3.5 adversarial tests
- V3 authority regression suite
- Claim Lock regression suite
- full API suite
- static analysis and type checking

## 15. Acceptance blockers

Implementation acceptance must be denied if any of the following exist:

- second truth validator
- second Claim Lock validator
- provenance rewrite
- classification downgrade
- cross-tenant composition
- silent conflict resolution
- presentation-to-protected promotion
- nondeterministic ordering
- provider dependency in the pure core
- authoritative output from `BLOCK` or `ERROR` inputs
- untraceable composition entries
