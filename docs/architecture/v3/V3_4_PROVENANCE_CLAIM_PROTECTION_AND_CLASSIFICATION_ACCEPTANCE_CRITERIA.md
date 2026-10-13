# Humanize V3.4 Provenance, Claim Protection, and Classification Acceptance Criteria

## Status

```text
V3_4_ACCEPTANCE_CRITERIA_STATUS=NONCANONICAL_CANDIDATE
V3_4_IMPLEMENTATION_AUTHORITY=NONE
```

These criteria govern acceptance of the V3.4 architecture package.

They do not constitute runtime acceptance.

## A. Exact package identity

Acceptance requires exactly four candidate documents:

```text
docs/architecture/v3/V3_4_PROVENANCE_CLAIM_PROTECTION_AND_CLASSIFICATION_ACTIVATION.md
docs/architecture/v3/V3_4_PROVENANCE_CLAIM_PROTECTION_AND_CLASSIFICATION_ARCHITECTURE.md
docs/architecture/v3/V3_4_AUTHORITY_PRESERVATION_AND_CLASSIFICATION_MATRIX.md
docs/architecture/v3/V3_4_PROVENANCE_CLAIM_PROTECTION_AND_CLASSIFICATION_ACCEPTANCE_CRITERIA.md
```

No application source, tests, dependency manifest, persistence schema, or
runtime configuration belongs to this architecture package.

## B. Canonical Humanize baseline

Acceptance requires exact binding to:

```text
HUMANIZE_CANONICAL_MAIN=
b6fed45818f244aa52f1a4727651478fdeb6e60a

HUMANIZE_CANONICAL_TREE=
4e0262be550f8ce7723f3de110bb84f2f8bc4af1

V3_3_R1R6_STATUS=
CANONICALLY_CLOSED_TERMINAL
```

V3.4 must not reopen V3.3.

## C. Canonical source-object binding

Acceptance requires the source-object identities recorded by the activation
document to match the canonical Humanize baseline.

Any mismatch requires a new review.

## D. Canonical V3.4 scope

Acceptance requires architecture coverage for exactly the phase-plan scope:

1. provenance graph/reference model;
2. protected authoritative facts;
3. Claim Lock integration;
4. classification propagation;
5. authority-preserving transformations;
6. negative tests for assumption-to-fact conversion;
7. cross-tenant protection.

The package must not silently expand into V3.5 governed composition.

## E. Truth-authority boundary

Acceptance requires:

- NEXUS remains authoritative for upstream truth;
- Humanize remains downstream;
- Protected Delivery Facts do not become upstream evidence authority;
- presentation does not become evidence authority;
- Humanize does not mutate NEXUS state;
- downstream governance does not imply stronger upstream approval.

## F. V3.3 interlock

Acceptance requires preservation of:

```text
V3_3_CLASSIFICATION_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
V3_3_PROVENANCE_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
```

V3.4 must not reinterpret a V3.3 rejection, validation outcome, source bundle,
or upstream authority.

## G. Provenance architecture

Acceptance requires the package to define architecture for:

- resolvable source-authority references;
- protected-fact derivation;
- presentation derivation;
- provenance preservation through downstream transformation;
- tenant and engagement consistency;
- fail-closed handling when required provenance cannot be established.

The package must not select a physical graph database or persistence model.

## H. Protected Delivery Fact architecture

Acceptance requires a Protected Delivery Fact to remain:

- tenant-bound;
- engagement-bound where applicable;
- source-traceable;
- provenance-bound;
- classification-bound;
- protected against presentation drift.

A Protected Delivery Fact must not:

- convert an assumption into a fact;
- modify an architecture decision;
- change an evaluation outcome;
- remove provenance;
- weaken classification;
- claim stronger upstream approval.

## I. Claim Lock integration

Acceptance requires explicit preservation of the existing Claim Lock control
boundary.

The architecture must not authorize:

- a second Claim Lock engine;
- a second Claim Lock validator;
- a second workspace policy repository;
- a second authorization resolver;
- semantic-equivalence claims unsupported by the existing Claim Lock contract.

Existing deterministic term/value preservation may be referenced as a future
integration point.

## J. Semantic protected-claim boundary

Acceptance requires recognition that the existing Claim Lock contract does not
deterministically prove semantic claim equivalence.

V3.4 must not treat exact-string claim presence or absence as a general
semantic truth test.

Any future semantic preservation control requires separately reviewed
authority.

## K. Classification propagation

Acceptance requires:

- source classification is retained as the minimum handling boundary;
- stricter downstream handling may be permitted later;
- silent downgrade is prohibited;
- classification remains attached through downstream governance;
- unknown required classification authority fails closed.

The package must not invent a taxonomy or label ordering.

## L. Authority-preserving transformations

Acceptance requires the package to define an authority envelope that preserves,
where applicable:

- source identity;
- provenance;
- classification;
- tenant;
- engagement;
- approval meaning;
- architecture decision meaning;
- evaluation outcome;
- material scope;
- uncertainty or assumption status.

A transformation that changes these semantics is not authority-preserving.

## M. Assumption-to-fact negative acceptance

Acceptance requires explicit negative cases proving the architecture rejects
or blocks:

- assumption to fact;
- hypothesis to completed outcome;
- proposal to approved decision;
- unresolved item to resolved state;

unless new authoritative source evidence independently establishes the changed
state.

## N. Evaluation protection

Acceptance requires explicit protection against:

- failure to success;
- inconclusive to success;
- not-evaluated to evaluated-success;
- partial result to complete success.

Presentation may explain an evaluation but must not rewrite its authoritative
outcome.

## O. Architecture-decision protection

Acceptance requires architecture decisions to retain their authoritative
meaning, source reference, and material constraints.

Humanize may summarize but must not silently substitute a different decision.

## P. Cross-tenant protection

Acceptance requires cross-tenant negative coverage.

At minimum, the architecture must reject:

- foreign-tenant source references;
- foreign-tenant protected facts;
- foreign-tenant classification context;
- foreign-tenant Claim Lock governance reuse;
- authority inferred from matching text or identifiers.

## Q. Engagement isolation

Acceptance requires engagement-specific authority to remain engagement-bound.

Cross-engagement reuse requires separately reviewed reusable-artifact
authority.

## R. Presentation-only content

Acceptance requires presentation-only material to remain distinguishable from
authoritative evidence.

Generated narrative must not silently become a Protected Delivery Fact or
source evidence.

## S. Fail-closed posture

Acceptance requires fail-closed behavior when required authority cannot be
established.

Examples include:

- missing source reference;
- dangling provenance;
- tenant mismatch;
- engagement mismatch;
- unknown required classification semantics;
- attempted classification downgrade;
- protected fact/source mismatch;
- unsupported authority transformation.

Exact runtime error types remain later work.

## T. V3.5 boundary

Acceptance requires V3.5 Governed Composition to remain separate.

V3.4 does not authorize:

- composition runtime;
- provider calls;
- template rendering;
- document generation;
- presentation generation;
- approval runtime;
- export;
- client release.

## U. Implementation non-selection

Acceptance requires the package not to select executable details prematurely.

The following remain unresolved until later separately reviewed gates:

- concrete provenance storage;
- concrete Protected Delivery Fact types;
- Claim Lock runtime adapter;
- classification policy engine;
- API surface;
- UI surface;
- persistence schema;
- migrations;
- dependencies;
- deployment architecture.

## V. Cross-cutting V3 obligations

Acceptance requires continued consideration of:

1. approved NEXUS schema compatibility where applicable;
2. compatibility fixtures;
3. tenant isolation;
4. classification enforcement;
5. provenance validation;
6. export authorization;
7. security review;
8. cross-tenant negative acceptance;
9. NEXUS runtime independence;
10. presentation-authority non-escalation.

## W. Explicit non-authority

Architecture-package acceptance must preserve:

```text
V3_4_IMPLEMENTATION_AUTHORITY=NONE
CLAIM_LOCK_RUNTIME_AUTHORITY=NONE
PROTECTED_DELIVERY_FACT_RUNTIME_AUTHORITY=NONE
PROVENANCE_GRAPH_RUNTIME_AUTHORITY=NONE
CLASSIFICATION_TRANSFORMATION_RUNTIME_AUTHORITY=NONE
COMPOSITION_RUNTIME_AUTHORITY=NONE
APPROVAL_RUNTIME_AUTHORITY=NONE
EXPORT_RUNTIME_AUTHORITY=NONE
CLIENT_RELEASE_AUTHORITY=NONE
API_ROUTE_AUTHORITY=NONE
UI_AUTHORITY=NONE
PERSISTENCE_IMPLEMENTATION_AUTHORITY=NONE
DATABASE_SCHEMA_AUTHORITY=NONE
MIGRATION_AUTHORITY=NONE
DEPENDENCY_INSTALLATION_AUTHORITY=NONE
DEPLOYMENT_AUTHORITY=NONE
```

## X. Architecture-package lifecycle

Detached candidate preparation does not establish canonical V3.4 architecture.

Canonicalization requires separately reviewed repository materialization,
staging, commit, publication, and canonical acceptance steps appropriate to the
governed repository.

Only after architecture closure may a separate V3.4 implementation-readiness
review consider executable work.

## Final acceptance invariant

The package passes only if it establishes a downstream authority-preservation
architecture that protects provenance, authoritative facts, classification,
tenant boundaries, and source meaning without acquiring upstream truth
authority or preempting V3.5.
