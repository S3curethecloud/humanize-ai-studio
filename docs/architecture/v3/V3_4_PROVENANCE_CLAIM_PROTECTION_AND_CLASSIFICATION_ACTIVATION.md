# Humanize V3.4 Provenance, Claim Protection, and Classification Activation

## Status

```text
V3_4_ARCHITECTURE_PACKAGE_STATUS=NONCANONICAL_CANDIDATE
V3_4_PHASE=Provenance, Claim Protection, and Classification
V3_4_ACTIVATION_AUTHORITY=ARCHITECTURE_PACKAGE_PREPARATION_ONLY
V3_4_IMPLEMENTATION_AUTHORITY=NONE
```

This document is a V3.4 architecture-activation candidate.

It does not authorize runtime implementation, repository materialization,
persistence changes, API routes, UI work, dependency changes, deployment,
export, or client release.

## Purpose

Activate bounded architecture planning for V3.4:

```text
Preserve source authority through Humanize delivery workflows.
```

V3.4 defines how downstream Humanize delivery state may preserve provenance,
protect authoritative facts, propagate classification, and perform
authority-preserving transformations without becoming an alternative source of
engagement truth.

## Canonical Humanize baseline

```text
HUMANIZE_CANONICAL_MAIN=
b6fed45818f244aa52f1a4727651478fdeb6e60a

HUMANIZE_CANONICAL_TREE=
4e0262be550f8ce7723f3de110bb84f2f8bc4af1

V3_3_R1R6_STATUS=
CANONICALLY_CLOSED_TERMINAL
```

V3.3 is not reopened by V3.4.

## Canonical source locks

This candidate is derived from these exact Humanize source objects:

| Source | Git blob |
| --- | --- |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_PHASE_PLAN.md` | `92b506c7e1d06a229f6669defa29b8eab8106eb0` |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_SYSTEM_BOUNDARY.md` | `01121fee2a60bb675a9ad82b4040da85b9a5ae75` |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_ACCEPTANCE_CRITERIA.md` | `5681e17207987b5fcfe8f360c4f403394db06f04` |
| `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_MODEL.md` | `d2e0c76030d867a47d09414de5df5cc0056412c8` |
| `docs/architecture/v3/V3_3_NDEB_BUNDLE_INGESTION_AND_VALIDATION_ACTIVATION.md` | `c5bc8ed4e798ba5e144dc0501ea7d208c24182cc` |
| `docs/architecture/v3/V3_3_NDEB_INGESTION_AND_VALIDATION_ARCHITECTURE.md` | `8eb52df12030611da3abd7e84c2e86e02e47f94e` |
| `docs/architecture/v3/V3_3_NDEB_BUNDLE_INGESTION_AND_VALIDATION_ACCEPTANCE_CRITERIA.md` | `f78c82a275148633a4358b9381500ec4892b9abd` |
| `docs/architecture/NEXUS_CLIENT_DELIVERY_ADAPTER_CONTRACT.md` | `865640d42a4136430b039f36e053ede1452fb9bb` |
| `docs/release/CLAIM_LOCK_V2_3_RELEASE.md` | `c7625b777ef25f9aab3668f3fff5489845cdc9dc` |
| `docs/architecture/ENTERPRISE_CLAIM_LOCK_GOVERNANCE_V2_12.md` | `7389e6882d90e588b7deb1446125540ee977ff07` |
| `docs/architecture/ENTERPRISE_CLAIM_LOCK_RUNTIME_GOVERNANCE_V2_12.md` | `529d24c7519e8cddf60268e6c41f56b32990fcc5` |

These source locks establish the planning evidence for this candidate. They do
not grant executable authority.

## V3.3 interlock

V3.3 owns validation and preservation at the read-only NDEB consumption
boundary.

Its authority remains:

```text
V3_3_CLASSIFICATION_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
V3_3_PROVENANCE_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
```

V3.4 owns the later downstream architecture for:

- provenance graph/reference behavior;
- protected authoritative facts;
- Claim Lock integration;
- classification propagation;
- authority-preserving transformations;
- negative acceptance for assumption-to-fact conversion;
- cross-tenant protection.

V3.4 must not reinterpret V3.3 validation outcomes or mutate the accepted
source bundle.

## Candidate scope

The canonical V3 phase plan reserves exactly these areas for V3.4:

1. provenance graph/reference model;
2. protected authoritative facts;
3. Claim Lock integration;
4. classification propagation;
5. authority-preserving transformations;
6. negative tests for assumption-to-fact conversion;
7. cross-tenant protection.

## Truth-authority doctrine

NEXUS remains authoritative for upstream engagement truth, evidence,
architecture decisions, evaluations, approvals, classification, provenance,
and deterministic evidence export.

Humanize V3.4 may preserve and govern downstream representations of approved
truth.

Humanize V3.4 must not:

- invent implementation outcomes;
- inflate delivery scope;
- convert assumptions into facts;
- change architecture decisions;
- modify evaluation results;
- weaken source classification;
- silently remove provenance;
- strengthen upstream approval state;
- manufacture a new source authority.

## Claim Lock integration doctrine

Existing Claim Lock control semantics remain authoritative where reused.

V3.4 architecture may define a future integration of Claim Lock with protected
delivery facts, but this package does not authorize a second Claim Lock engine,
a second validator, a second policy repository, or a new authorization
resolver.

The existing V2.3 control contract remains the reference for deterministic
term and literal-value preservation.

The existing V2.3 boundary that semantic protected claims are not
deterministically proven equivalent by exact-string preservation must remain
visible.

V3.4 must not claim semantic equivalence merely because a protected claim can
be represented or referenced.

## Protected delivery facts

A Protected Delivery Fact is downstream Humanize state that represents approved
source material requiring protection against presentation drift.

It must:

- remain tenant-bound;
- remain engagement-bound where applicable;
- retain resolvable source-authority references;
- retain required provenance;
- retain the applicable classification floor;
- preserve the authoritative value or decision it represents;
- remain distinguishable from presentation-only narrative.

A Protected Delivery Fact does not become upstream evidence authority.

## Provenance doctrine

Every material downstream fact must remain resolvable to its required source
authority.

A downstream transformation may add presentation lineage but must not replace,
erase, or rewrite authoritative source lineage.

Missing required provenance fails closed.

## Classification doctrine

Humanize must preserve source classification.

Humanize may later apply stricter handling controls.

Humanize must not silently downgrade source classification.

This package does not invent a classification taxonomy or an ordering between
labels that is not already established by an authoritative source.

Exact runtime classification-policy resolution remains later work.

## Authority-preserving transformation doctrine

A transformation is authority-preserving only when the resulting delivery
state does not claim more truth, approval, certainty, scope, or authorization
than the authoritative source establishes.

Presentation adaptation may change wording, organization, style, or audience
level only when protected facts, classification, provenance, and source
authority remain intact.

## Tenant and engagement boundary

Cross-tenant mixing is prohibited.

Cross-engagement authority reuse is prohibited unless a later explicitly
reviewed contract establishes a safe reusable-artifact class.

Similarity of text, identifiers, filenames, or presentation structure is not
authority to cross an isolation boundary.

## V3.5 interlock

V3.5 Governed Composition is the successor phase.

V3.4 may define the protected, classified, provenance-bound inputs that later
composition may consume.

V3.4 does not authorize governed composition runtime, content generation,
template rendering, document generation, or presentation generation.

## Package contents

This V3.4 candidate consists of exactly four documents:

```text
docs/architecture/v3/V3_4_PROVENANCE_CLAIM_PROTECTION_AND_CLASSIFICATION_ACTIVATION.md
docs/architecture/v3/V3_4_PROVENANCE_CLAIM_PROTECTION_AND_CLASSIFICATION_ARCHITECTURE.md
docs/architecture/v3/V3_4_AUTHORITY_PRESERVATION_AND_CLASSIFICATION_MATRIX.md
docs/architecture/v3/V3_4_PROVENANCE_CLAIM_PROTECTION_AND_CLASSIFICATION_ACCEPTANCE_CRITERIA.md
```

## Explicit non-authority

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
PYPROJECT_MUTATION_AUTHORITY=NONE
PACKAGE_LOCK_MUTATION_AUTHORITY=NONE
DEPLOYMENT_AUTHORITY=NONE
NEXUS_SOURCE_MUTATION_AUTHORITY=NONE
```

## Candidate effective point

Preparing or independently accepting this detached package does not make V3.4
canonical.

Canonical architecture requires a separately authorized repository lifecycle.

Even canonical architecture does not automatically grant V3.4 runtime
implementation authority.

## Final invariant

Humanize may transform how approved truth is presented.

Humanize may not transform what that truth is.
