# Humanize V3.2 Client Delivery Domain Model

## Status

V3.2 domain-architecture candidate.

This document defines conceptual Humanize client-delivery domain ownership.

It does not define executable Python classes, Pydantic models, API schemas,
database tables, or serialization formats.

## Purpose

Define the Humanize-owned downstream domain needed for governed client
delivery while preserving NEXUS as the upstream source of engagement truth.

The model establishes domain identity, relationships, ownership, isolation,
and authority invariants.

## Domain-model doctrine

The V3.2 domain model follows these rules:

1. Humanize owns downstream delivery state only.
2. NEXUS remains authoritative for upstream engagement truth.
3. Every material Humanize delivery object remains tenant-bound.
4. Every engagement-specific Humanize delivery object remains
   engagement-bound.
5. Upstream authority is referenced, not recreated.
6. Persistence does not elevate presentation state into evidence authority.
7. Later-phase behavior is not activated merely because its future record type
   is represented here.
8. Unknown or ambiguous authority fails closed.

## Conceptual identity model

V3.2 requires explicit identity at the architecture level.

The implementation representation and concrete data types are deferred.

### Tenant identity

Every client-delivery aggregate must identify the Humanize tenant that owns the
downstream state.

Tenant identity is an isolation boundary.

It is not optional metadata.

### Engagement identity

Delivery state associated with a client engagement must remain bound to the
corresponding engagement identity.

Humanize must not infer engagement identity from presentation text or local
storage location.

### Humanize object identity

Each persisted Humanize delivery object must have a stable Humanize-side
identity appropriate to its domain role.

A Humanize object identity does not replace or redefine an upstream source
identity.

### Source-authority reference

Objects derived from, presenting, or protecting approved source evidence must
retain a resolvable source-authority reference when such authority is required.

The reference must not be converted into an untraceable local narrative.

## Delivery Workspace

A Delivery Workspace is the Humanize-owned aggregate boundary for downstream
client-delivery work.

A Delivery Workspace must:

- belong to exactly one Humanize tenant;
- remain associated with the intended engagement context;
- provide the ownership boundary for Humanize delivery state;
- distinguish Humanize delivery state from upstream engagement truth;
- prevent foreign-tenant delivery state from being attached silently.

A Delivery Workspace may eventually associate:

- imported-bundle references;
- delivery artifacts;
- protected delivery facts;
- source-evidence references;
- Humanize approval records;
- export-authorization records;
- delivery manifests;
- handoff packages.

The exact executable aggregate implementation is not defined in V3.2.

## Imported Bundle Reference

An Imported Bundle Reference is a Humanize-side reference to an upstream
delivery-evidence bundle accepted through a future authorized consumption
boundary.

V3.2 establishes only the conceptual domain role.

The record must not imply that a live NDEB schema is currently bound.

The record must not imply that ingestion runtime currently exists.

When V3.3 is separately authorized, an Imported Bundle Reference must preserve
the authoritative identity and integrity information exposed by the approved
upstream contract.

Humanize must not synthesize upstream identity values.

Bundle ingestion, validation, rejection, and compatibility enforcement remain
V3.3 responsibilities.

## Delivery Artifact

A Delivery Artifact represents Humanize-owned downstream artifact state.

It may represent the identity and governed state of presentation material that
is created in later delivery phases.

A Delivery Artifact must remain bound to:

- its tenant;
- its engagement context when applicable;
- its Humanize delivery workspace;
- required source-authority references;
- applicable classification;
- applicable Humanize approval and export state when those later phases are
  authorized.

V3.2 does not authorize DOCX, PDF, PPTX, or any other file generation.

DOCX and PDF generation remain V3.8 responsibilities.

PPTX and executive presentation generation remain V3.9 responsibilities.

## Protected Delivery Fact

A Protected Delivery Fact is a Humanize downstream representation of approved
source material that requires protection against presentation drift.

It must not create new evidence authority.

It must remain traceable to source authority.

A Protected Delivery Fact must not:

- convert an assumption into a fact;
- modify an architecture decision;
- change an evaluation outcome;
- remove provenance;
- weaken classification;
- claim stronger upstream approval than the source provides.

Exact claim-protection and classification behavior remain V3.4
responsibilities.

## Source Evidence Reference

A Source Evidence Reference preserves the relationship between Humanize
delivery state and authoritative source evidence.

It is an authority reference, not a local redefinition of evidence.

A Source Evidence Reference must preserve enough information, when made
available through an authorized upstream contract, to permit deterministic
resolution of the source authority required by the downstream workflow.

V3.2 does not define NDEB wire fields.

V3.2 does not define NEXUS database identifiers.

V3.2 does not authorize direct NEXUS database access.

## Approval Record

An Approval Record represents Humanize-side approval evidence for downstream
presentation or delivery work.

It must remain separate from upstream NEXUS approval authority.

A Humanize approval must not rewrite:

- an upstream evidence approval;
- an architecture approval;
- an evaluation approval;
- delivery-readiness truth held by NEXUS.

V3.2 establishes the conceptual record only.

Exact approval states, transitions, actors, decision rules, and lifecycle
semantics remain V3.6 responsibilities.

## Export Authorization Record

An Export Authorization Record represents the Humanize-side record boundary
for a future explicit export decision.

The existence of this domain concept does not authorize export.

Generation authority and export authority remain distinct.

V3.2 does not define the executable export decision process.

Exact export-authorization semantics remain V3.7 responsibilities.

## Delivery Manifest

A Delivery Manifest represents the conceptual Humanize aggregate needed to
bind a governed delivery to its constituent identities and authority evidence.

V3.2 establishes the domain boundary only.

Manifest construction, required manifest content, export-decision binding, and
runtime validation remain V3.7 responsibilities.

A Delivery Manifest must not become upstream evidence authority.

## Handoff Package

A Handoff Package represents the Humanize-owned identity of a future complete
client handoff assembly.

The package may eventually reference previously approved artifacts, manifests,
approval evidence, classification information, provenance references, and
export decisions.

V3.2 does not authorize handoff-package construction.

Complete handoff-package assembly remains V3.10 responsibility.

A Handoff Package is governed delivery state.

It is not the upstream source of engagement truth.

## Domain relationships

The architecture requires these relationships:

- a Delivery Workspace owns Humanize downstream delivery state;
- an Imported Bundle Reference belongs to the correct Delivery Workspace;
- a Source Evidence Reference resolves authority required by downstream
  delivery state;
- a Protected Delivery Fact refers to authoritative source evidence;
- a Delivery Artifact belongs to the correct Delivery Workspace;
- an Approval Record applies only within its authorized Humanize delivery
  context;
- an Export Authorization Record applies only to the governed delivery context
  it actually authorizes;
- a Delivery Manifest binds governed Humanize delivery identities without
  becoming upstream truth;
- a Handoff Package references approved Humanize delivery components rather
  than manufacturing their authority.

The exact relational storage representation is deferred.

## Tenant isolation

Cross-tenant mixing is prohibited.

A record from tenant A must not be attached to tenant B merely because:

- identifiers have compatible syntax;
- artifacts have matching filenames;
- evidence has similar content;
- an engagement name is similar;
- local storage paths overlap;
- a downstream user can access both workspaces.

Tenant identity must be evaluated as an authority boundary.

## Engagement isolation

Engagement-specific delivery state must remain bound to its intended
engagement.

Humanize must not infer engagement equivalence from narrative similarity.

A reference valid for one engagement must not silently authorize use in
another engagement.

## Classification invariant

Domain state that carries or represents classified source material must
preserve the applicable source classification boundary.

Humanize may later apply stricter handling.

Humanize must not silently reduce source classification.

Exact propagation behavior remains V3.4 responsibility.

## Provenance invariant

A presentation transformation must not sever the relationship to required
source authority.

Protected delivery state must retain the provenance information required by
later reviewed phases.

V3.2 defines the invariant.

It does not implement the provenance graph.

## Persistence invariant

Persisting a domain object does not make the object authoritative upstream
truth.

Persisting a local copy does not supersede its source evidence.

Persisting approval or export records does not grant the underlying decision
authority unless the responsible later phase has been separately authorized.

## Lifecycle non-authority

V3.2 may define record boundaries required by later lifecycle phases.

V3.2 does not define:

- bundle-ingestion runtime;
- claim-protection runtime;
- composition runtime;
- approval state machines;
- export state machines;
- document-generation workflows;
- handoff-package assembly workflows.

## Implementation mapping

Executable classes, repository protocols, persistence mappings, table names,
column names, indexes, migrations, service APIs, and HTTP models require a
future separately reviewed implementation gate.

No implementation mapping is canonicalized by this document.

## Final invariant

Humanize domain objects may represent governed downstream delivery state.

They must never erase the distinction between downstream presentation state
and upstream authoritative truth.
