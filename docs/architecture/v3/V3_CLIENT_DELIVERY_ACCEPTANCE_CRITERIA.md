
# Humanize V3 Client Delivery Acceptance Criteria
## Status

V3.0 activation acceptance candidate.

These criteria govern acceptance of the V3 architecture activation package and
establish minimum cross-cutting obligations for later V3 phases.

They do not grant runtime implementation authority.

## A. Canonical predecessor

Acceptance requires:

- Humanize V2.13 R4 EvalOps remains canonically closed;
- activation begins from the approved V2.13 canonical main;
- the repository is clean before activation-package creation;
- the activation package introduces architecture documents only.
## B. Exact activation-package boundary

The V3.0 package contains exactly:

```text
docs/architecture/v3/V3_CLIENT_DELIVERY_ACTIVATION.md
docs/architecture/v3/V3_CLIENT_DELIVERY_SYSTEM_BOUNDARY.md
docs/architecture/v3/V3_CLIENT_DELIVERY_PHASE_PLAN.md
docs/architecture/v3/V3_CLIENT_DELIVERY_ACCEPTANCE_CRITERIA.md
```

No application source, tests, dependency manifests, runtime configuration, or
generated artifacts belong to the activation package.

## C. Truth-authority boundary

Acceptance requires all of the following:

- NEXUS remains authoritative for engagement truth;
- Humanize remains downstream;
- Humanize does not become an alternative system of record;
- presentation never becomes evidence authority;
- generated narrative does not become authoritative evidence;
- Humanize does not modify NEXUS state.
## D. NDEB ownership boundary

Acceptance requires:

- NDEB schema authority remains NEXUS-owned;
- deterministic NDEB generation remains NEXUS-owned;
- Humanize may define only consumer-side compatibility requirements;
- live adapter implementation remains blocked until an approved canonical
NEXUS exchange schema exists;
- Humanize never treats its compatibility profile as the upstream schema.
## E. Integration boundary

Humanize must not:

- scrape NEXUS repositories;
- access NEXUS internal databases;
- depend on undocumented NEXUS implementation classes;
- infer project truth from unstructured history;
- consume unverified generated summaries as truth;
- become a NEXUS runtime dependency.
## F. Provenance

Every later material client-delivery claim must be traceable to authoritative
source evidence or explicitly classified as presentation-only content.

Provenance must survive authorized:

- ingestion;
- normalization;
- composition;
- approval;
- generation;
- manifest construction;
- export.

Missing required provenance must fail closed.

## G. Tenant isolation

Later implementation must prove:

- bundle tenant identity is validated;
- delivery workspaces are tenant-bound;
- source evidence references are tenant-bound;
- generated artifacts are tenant-bound;
- approvals are tenant-bound;
- manifests are tenant-bound;
- export authorization is tenant-bound;
- foreign-tenant evidence is rejected.

Cross-tenant negative acceptance is mandatory.

## H. Classification

Humanize must preserve source classification.

Humanize may strengthen handling controls.

Humanize must not silently weaken classification.

Classification must remain attached through the complete delivery lifecycle.

## I. Claim protection

Later implementation must prove that protected authoritative delivery facts
cannot be silently changed by:

- rewriting;
- summarization;
- audience adaptation;
- template rendering;
- document generation;
- presentation generation.

Assumptions must not silently become facts.

Evaluation failures must not silently become successes.

Architecture decisions must not be rewritten into different decisions.

## J. Approval separation

The architecture must preserve these distinctions:

```text
source evidence approved
!=
delivery content composed
!=
delivery content approved
!=
artifact generated
!=
export authorized
!=
client released
```

Human approval is required before client release.

Exact lifecycle states remain phase-owned.

## K. Export authorization

Artifact generation must not imply export authorization.

Later export decisions must evaluate at least:

- tenant;
- engagement;
- artifact;
- artifact version;
- classification;
- approval state;
- manifest;
- intended audience;
- allowed delivery context.
## L. NEXUS independence

Acceptance requires NEXUS remain independently capable of:

- architecture reasoning;
- runtime operation;
- evidence creation;
- deterministic evidence export;
- baseline deterministic client deliverable rendering.

Humanize may be optional advanced delivery.

Humanize must not become mandatory for NEXUS operation.

## M. Phase discipline

The approved candidate phase sequence is:

```text
V3.0   Doctrine and System Boundary
V3.1   NDEB Consumption Contract and Compatibility Profile
V3.2   Client Delivery Domain and Persistence
V3.3   Bundle Ingestion and Validation
V3.4   Provenance, Claim Protection, and Classification
V3.5   Governed Composition
V3.6   Human Approval Lifecycle
V3.7   Delivery Manifest and Export Authorization
V3.8   DOCX and PDF Delivery
V3.9   PPTX and Executive Delivery
V3.10  Complete Client Handoff Package
```

Each phase requires separate authority.

The activation package does not authorize implementation of any listed phase.

## N. Policies and Settings deferral

Acceptance requires:

- Policies remains planned;
- Settings remains planned;
- neither is treated as a V3 prerequisite;
- V3 does not silently activate either surface.
## O. V3.0 closure

V3.0 may be declared closed only after:

1. exact four-document package creation;
2. package creation acceptance review;
3. bounded staging and commit;
4. commit acceptance review;
5. bounded push;
6. push acceptance review;
7. pull-request creation;
8. pull-request acceptance;
9. canonical merge;
10. post-merge verification.

Until then:

```text
V3_0_STATUS = CANDIDATE
V3_IMPLEMENTATION_AUTHORITY = NONE
NEXUS_ADAPTER_IMPLEMENTATION_AUTHORITY = NONE
CLIENT_DELIVERY_UI_AUTHORITY = NONE
CLIENT_DELIVERY_PERSISTENCE_AUTHORITY = NONE
EXPORT_GENERATION_AUTHORITY = NONE
```
## P. Failure posture

Acceptance fails if the package:

- gives Humanize NDEB schema authority;
- gives Humanize NDEB generation authority;
- weakens NEXUS truth authority;
- authorizes runtime implementation;
- activates Client Delivery UI;
- activates persistence;
- activates export generation;
- activates Policies;
- activates Settings;
- creates a NEXUS runtime dependency;
- permits presentation to become evidence authority.
## Final acceptance invariant

V3.0 succeeds when Humanize has a canonical, bounded architecture foundation
for advanced client delivery without gaining authority over upstream truth or
prematurely gaining runtime implementation authority.
