# Humanize V3.4 Provenance, Claim Protection, and Classification Architecture

## Status

```text
V3_4_ARCHITECTURE_STATUS=NONCANONICAL_CANDIDATE
V3_4_IMPLEMENTATION_AUTHORITY=NONE
```

This document defines candidate V3.4 architecture.

It does not define executable Python classes, Pydantic models, API schemas,
database tables, transport formats, or deployment configuration.

## Architecture objective

Create a downstream authority-preservation layer between validated V3.3
evidence consumption and later V3.5 governed composition.

The layer must ensure that downstream delivery work remains traceable to
authoritative source evidence and cannot silently weaken classification,
rewrite authoritative facts, or promote assumptions into facts.

## Position in the V3 flow

```text
V3.3 validated read-only evidence
        |
        v
source-authority references
        |
        v
V3.4 provenance + protected facts + classification
        |
        v
authority-preserving delivery state
        |
        v
V3.5 governed composition
```

V3.4 begins only after source material is eligible for downstream Humanize use.

V3.4 does not replace V3.3 validation.

## Authority model

### Upstream authority

Authoritative upstream truth remains external to V3.4.

V3.4 does not own:

- engagement truth;
- architecture decisions;
- evaluation outcomes;
- source evidence;
- upstream approval state;
- upstream classification authority;
- upstream provenance authority.

### Humanize downstream authority

V3.4 may define Humanize-owned governance state needed to preserve that truth
through delivery workflows.

That governance state is downstream and must remain visibly subordinate to its
source authority.

## Conceptual provenance model

V3.4 requires a provenance reference model capable of representing, at the
architecture level:

- the authoritative source reference;
- the Humanize tenant;
- the engagement context where applicable;
- the source classification;
- the downstream object identity;
- the transformation or derivation relationship;
- the protected-fact relationship where applicable;
- the source approval/evaluation identity when material to the claim;
- presentation-only lineage where generated narrative is introduced.

Exact executable identifiers and serialization are deferred.

## Provenance relationship classes

The architecture distinguishes at least these conceptual relationships:

### Source reference

A direct reference from Humanize delivery state to authoritative source
evidence.

### Protected-fact derivation

A relationship showing that a Humanize Protected Delivery Fact represents
specific approved source material.

### Presentation derivation

A relationship showing that narrative or presentation state was derived from
approved downstream material.

Presentation derivation does not create evidence authority.

### Supersession reference

Where later approved source evidence supersedes earlier source evidence, a
downstream record may refer to the authoritative supersession relationship.

Humanize must not invent supersession merely because two statements conflict.

## Provenance invariants

Required provenance must:

- remain resolvable;
- remain tenant-consistent;
- remain engagement-consistent where applicable;
- survive authorized transformation;
- remain attached to protected delivery facts;
- remain available to later approval, manifest, export, and handoff phases.

The architecture must fail closed when required source authority cannot be
established.

## Protected Delivery Fact architecture

A Protected Delivery Fact represents approved source material that is material
enough to require protection from presentation drift.

Conceptually, a protected fact must preserve:

- Humanize object identity;
- tenant identity;
- engagement identity where applicable;
- source-authority reference;
- source provenance;
- source classification or stronger downstream handling;
- protected authoritative content or value;
- protection rationale or category where later authorized;
- downstream lineage to artifacts that consume it.

Exact executable fields are deferred.

## Protected-fact non-authority

A Protected Delivery Fact must not:

- create a fact that the source does not establish;
- elevate an assumption into a fact;
- rewrite an architecture decision;
- convert an evaluation failure into success;
- strengthen source approval;
- remove material caveats;
- erase source identity;
- weaken source classification.

## Claim Lock integration boundary

Claim Lock is a preservation control, not a truth-generation control.

A future V3.4 runtime may reuse the existing Claim Lock engine only through a
separately reviewed implementation design.

This architecture does not authorize:

- a second Claim Lock validator;
- a second workspace Claim Lock policy repository;
- a second authorization resolver;
- semantic equivalence claims unsupported by the existing Claim Lock contract.

Existing deterministic Claim Lock behavior is especially relevant for:

- protected terminology;
- exact literal values;
- strict fail-closed deterministic violations;
- audit-only evidence;
- precedence of factual verification authority over Claim Lock.

## Semantic protected claims

The existing V2.3 Claim Lock contract intentionally does not claim
deterministic semantic equivalence for protected claims.

V3.4 must preserve that boundary.

A future V3.4 design may bind semantic facts to authoritative source references
and other separately authorized verification controls, but it must not
misrepresent exact-string presence as proof of semantic equivalence.

## Classification propagation model

Classification is an authority-bearing handling property.

V3.4 requires classification to propagate through downstream delivery state.

Conceptually:

```text
source classification
        |
        v
protected delivery fact
        |
        v
derived delivery state
        |
        v
future composition / approval / generation / manifest / export
```

The downstream classification must never be weaker than the applicable source
classification unless a later separately reviewed upstream-compatible rule
explicitly authorizes the change.

Humanize may apply stricter handling.

## Classification taxonomy non-invention

This package does not define a new classification taxonomy.

It does not infer an ordering between labels merely from their names.

A later runtime gate must bind the authoritative classification vocabulary and
any valid ordering or compatibility rules before executable downgrade/upgrade
decisions are implemented.

## Authority-preserving transformations

A transformation is eligible only if it preserves the authority envelope of
its inputs.

The authority envelope includes, when applicable:

- source identity;
- provenance;
- classification;
- tenant;
- engagement;
- approval meaning;
- architecture decision meaning;
- evaluation outcome;
- material scope;
- explicit uncertainty or assumption status.

## Permitted transformation classes

Subject to later runtime authorization, V3.4 may permit transformations such
as:

- presentation reordering;
- audience-oriented wording changes;
- formatting changes;
- terminology adaptation that does not violate protected terminology;
- summarization that retains protected facts and material qualifications;
- derivation of presentation-only content explicitly marked as such.

These examples are architectural categories, not runtime authorization.

## Prohibited authority changes

A transformation must be rejected or blocked when it would:

- add an unsupported implementation outcome;
- remove a material failure;
- change an architecture decision;
- remove a required source reference;
- downgrade classification;
- mix foreign-tenant source authority;
- convert an assumption into a confirmed fact;
- convert an unresolved item into a completed outcome;
- represent presentation content as authoritative evidence;
- imply stronger approval than the source establishes.

## Assumption-to-fact protection

Assumption state is authority-bearing.

A later V3.4 implementation must prove that an assumption, hypothesis,
proposal, or unresolved statement cannot become a protected authoritative fact
without separately established source authority.

Narrative confidence is not evidence.

## Evaluation-outcome protection

Evaluation outcomes are authoritative source material.

A failed, partial, inconclusive, or not-evaluated result must not be rewritten
as success.

A downstream narrative may explain the result but may not alter its status.

## Architecture-decision protection

Architecture decisions must retain their authoritative meaning.

Humanize presentation may summarize a decision but must not silently replace
the selected decision, rationale, constraints, or recorded status with a new
decision.

## Cross-tenant protection

All V3.4 governance state is tenant-bound.

A source-authority reference, protected fact, classification context, or
provenance relationship from tenant A must not silently authorize downstream
state for tenant B.

Cross-tenant negative acceptance is mandatory.

## Engagement protection

Engagement-specific authority must remain engagement-bound.

Narrative similarity or identifier compatibility is not sufficient authority
for cross-engagement reuse.

## Failure posture

The future runtime must fail closed when required authority cannot be
established.

Architecture-level examples include:

- missing source-authority reference;
- dangling provenance;
- tenant mismatch;
- engagement mismatch;
- unknown required classification semantics;
- unsupported classification downgrade;
- protected-fact/source mismatch;
- missing material approval/evaluation reference;
- Claim Lock deterministic violation under strict enforcement;
- attempted assumption-to-fact conversion.

Exact runtime error types and API mappings are deferred.

## V3.5 handoff boundary

V3.4 may make governed downstream state eligible for V3.5 composition only
when the required authority envelope remains established.

V3.5 remains responsible for composition behavior.

V3.4 does not generate client narrative, DOCX, PDF, PPTX, manifests, or handoff
packages.

## Implementation selection remains unresolved

This architecture does not select:

- concrete provenance graph storage;
- relational or graph databases;
- event sourcing;
- Claim Lock adapter classes;
- API routes;
- UI models;
- classification policy engines;
- serialization formats;
- persistence migrations;
- package dependencies.

Those decisions require a later separately reviewed implementation-readiness
gate.

## Final architecture invariant

Every material downstream claim must preserve a resolvable path to the
authority that supports it.

Presentation may evolve.

Authority may not drift.
