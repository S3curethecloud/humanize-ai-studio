# HUMANIZE V3.5 — Governed Composition Reference Architecture R1

Status: DETACHED PLANNING CANDIDATE — NOT CANONICAL — NO IMPLEMENTATION AUTHORITY

## 1. Purpose

V3.5 introduces a deterministic, fail-closed Governed Composition layer that can assemble already validated and already V3.4-authorized content into a composition without changing the authority, provenance, classification, or protected-claim meaning of any input.

V3.5 does not determine truth. NEXUS remains the external truth authority. V3.5 does not reparse or revalidate NDEB, does not create a second Claim Lock validator, does not rewrite provenance, and does not infer a classification taxonomy.

## 2. Canonical predecessor boundary

The canonical predecessor is HUMANIZE V3.4 Provenance, Claim Protection and Classification at commit:

`7a7fcee04a2066eb0df57b553995f5d68e50ccc8`

V3.5 consumes V3.4-authorized results as immutable input constraints. The following V3.4 concepts remain authoritative and are not reimplemented:

- `AuthorityContext`
- `SourceAuthorityBinding`
- `ProtectedDeliveryFact`
- `PresentationDerivation`
- V3.4 authority dispositions: `ELIGIBLE`, `BLOCK`, `ERROR`, `PRESENTATION_ONLY`
- exact tenant and engagement bindings
- provenance and source-reference bindings
- classification preservation rules
- Claim Lock outcomes and evidence
- the distinction between protected facts and presentation-only derivations

## 3. Architectural goal

Given one or more V3.4-authorized inputs, V3.5 must produce either:

1. a deterministic Governed Composition envelope whose entries retain their original authority and evidence bindings; or
2. a fail-closed disposition with no authoritative composition output.

Composition is assembly, not truth synthesis.

## 4. Proposed provider-free namespace

The proposed implementation boundary is provider-free and pure:

`app.v3.composition`

Proposed modules, subject to later architecture acceptance:

- `contracts.py`
- `ordering.py`
- `conflicts.py`
- `identity.py`
- `service.py`

No provider adapter, renderer, persistence layer, human approval workflow, export path, or delivery-format code belongs in V3.5.

## 5. Proposed immutable contracts

### 5.1 CompositionInput

A `CompositionInput` wraps one already-authorized V3.4 content item and includes:

- immutable input identifier
- caller-declared composition position
- tenant identifier
- engagement identifier
- source artifact reference
- V3.4 authority disposition
- source authority binding
- provenance binding
- classification value
- content kind: `PROTECTED_FACT` or `PRESENTATION_DERIVATION`
- exact reference to the protected fact or presentation derivation
- Claim Lock evidence reference when applicable

The wrapper must not copy content into a new authority domain or alter the referenced V3.4 object.

### 5.2 CompositionRequest

A `CompositionRequest` contains:

- tenant identifier
- engagement identifier
- immutable tuple of `CompositionInput`
- composition purpose label
- optional requested output classification only when exactly equal to the inherited classification
- no truth override
- no provenance override
- no classification downgrade field
- no cross-tenant override

### 5.3 GovernedCompositionEntry

Each output entry preserves:

- original input identifier
- deterministic position
- content kind
- source artifact reference
- source authority binding
- provenance binding
- classification
- protected-fact reference or presentation-derivation reference
- authority disposition
- evidence references

An entry cannot be converted from `PRESENTATION_DERIVATION` to `PROTECTED_FACT`.

### 5.4 GovernedComposition

The successful envelope contains:

- `composition_id`
- tenant identifier
- engagement identifier
- immutable ordered entries
- aggregate classification value when an exact common value exists
- provenance ledger containing every input provenance binding
- source-authority ledger containing every input source authority binding
- protected-fact references
- presentation-derivation references
- composition kind: `AUTHORITATIVE`, `PRESENTATION`, or `MIXED`
- disposition: `ELIGIBLE` or `PRESENTATION_ONLY`
- deterministic evidence surface

A successful envelope contains no newly asserted protected delivery fact.

### 5.5 CompositionDecision

Every request yields one deterministic decision:

- `ELIGIBLE`
- `PRESENTATION_ONLY`
- `BLOCK`
- `ERROR`

`BLOCK` and `ERROR` produce no authoritative composition envelope.

## 6. Deterministic composition algorithm

The service executes the following order exactly:

1. Validate the request structure without reparsing NDEB.
2. Require at least one input.
3. Require unique immutable input identifiers.
4. Require unique explicit integer positions and sort by position.
5. Require request tenant and engagement to exactly match every input.
6. Require every input to carry an already-established V3.4 authority disposition.
7. If any input is `ERROR`, return `ERROR` with no authoritative output.
8. If any input is `BLOCK`, return `BLOCK` with no authoritative output.
9. Validate presence, not truth, of required provenance/source-authority bindings.
10. Require exact classification equality across authoritative protected-fact inputs; no taxonomy or hierarchy is inferred.
11. Reject any requested output classification that differs from the inherited exact value.
12. Detect protected-fact authority conflicts.
13. Preserve all presentation-only derivations as presentation-only.
14. Build ordered immutable entries without changing referenced content.
15. Produce provenance and source-authority ledgers containing all inputs.
16. Determine composition kind.
17. Compute the internal `composition_id` from canonical internal JSON.
18. Return `ELIGIBLE` only when authoritative protected-fact content is present and every authoritative rule passes.
19. Return `PRESENTATION_ONLY` when the composition has no authoritative protected-fact content.
20. Emit deterministic evidence describing every decision.

## 7. Ordering contract

Ordering is explicit rather than inferred.

- Each input must provide a unique integer position.
- Positions are sorted ascending.
- Duplicate positions are `ERROR`.
- Caller order without explicit positions is not authoritative.
- V3.5 performs no semantic ranking, relevance ranking, or model-based reordering.
- Different ordered requests may legitimately produce different `composition_id` values.

## 8. Conflict model

A protected-fact conflict exists when two inputs claim the same protected-fact binding key but do not have an identical protected-fact identity and authority/provenance surface.

V3.5 must never silently choose a winner.

Conflict outcomes:

- same tenant/engagement, same protected-fact identity, same authority/provenance surface: retain both input references or expose an explicit exact-duplicate evidence record; do not invent a new fact.
- same protected-fact binding key with different value identity, source authority, provenance, or classification: `BLOCK`.
- incompatible classification values among authoritative protected facts: `BLOCK`.
- cross-tenant or cross-engagement inputs: `BLOCK`.
- missing required authority/provenance structure: `ERROR`.

## 9. Classification propagation

V3.5 has no classification hierarchy and no downgrade authority.

Rules:

- one protected-fact classification value across the authoritative set: inherit exactly.
- differing authoritative classification values: `BLOCK`.
- requested output classification absent: inherit.
- requested output classification exactly equal: allowed.
- requested output classification unequal: `BLOCK`.
- presentation derivations retain their source classification and may not lower the authoritative classification.

## 10. Provenance preservation

Every output entry must remain traceable to the exact V3.4 provenance binding that authorized it.

V3.5 must not:

- rewrite source references
- replace evidence references
- collapse distinct provenance paths into an invented source
- substitute one authority binding for another
- present a composition hash as provenance

The provenance ledger is an aggregation of preserved bindings, not a new truth source.

## 11. Composition identity

`composition_id` is an internal deterministic identity only.

Proposed input to canonical hashing:

- schema/version marker
- tenant identifier
- engagement identifier
- composition purpose label
- ordered entry identity surfaces
- exact classification value
- source authority binding identities
- provenance binding identities
- protected-fact and presentation-derivation reference identities

Canonical JSON plus SHA-256 may be used.

The hash proves deterministic identity of the internal composition surface. It does not prove truth, approval, delivery authorization, or semantic correctness.

## 12. Authority separation

V3.5 may assemble existing authority-bearing content. It may not:

- create new NEXUS truth
- convert model output into protected truth
- approve content for human delivery
- authorize export
- render DOCX/PDF/PPTX
- mutate protected facts
- rewrite Claim Lock results
- weaken classification or provenance restrictions

## 13. Phase exclusions

Reserved for later phases:

- V3.6: Human Approval Lifecycle
- V3.7: Delivery Manifest and Export Authorization
- V3.8: DOCX/PDF Delivery
- V3.9: PPTX/Executive Delivery
- V3.10: Complete Client Handoff Package

## 14. Required architecture acceptance before implementation

Implementation may not begin until the architecture candidate independently proves:

- deterministic contract completeness
- authority preservation
- provenance preservation
- classification fail-closed behavior
- conflict fail-closed behavior
- cross-tenant isolation
- protected-fact/presentation separation
- stable ordering
- deterministic identity behavior
- explicit phase exclusions
- no second validation or truth authority
