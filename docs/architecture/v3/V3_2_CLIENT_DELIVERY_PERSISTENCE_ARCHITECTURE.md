# Humanize V3.2 Client Delivery Persistence Architecture

## Status

V3.2 persistence-architecture candidate.

This document defines persistence ownership and implementation constraints.

It does not create repositories, database tables, migrations, runtime
configuration, or external persistence adapters.

## Purpose

Define how future Humanize client-delivery state may be persisted without
turning Humanize into a shadow NEXUS system of record.

## Persistence ownership

Humanize may persist Humanize-owned downstream delivery state.

Candidate state includes architecture representations for:

- Delivery Workspace;
- Imported Bundle Reference;
- Delivery Artifact;
- Protected Delivery Fact;
- Source Evidence Reference;
- Approval Record;
- Export Authorization Record;
- Delivery Manifest;
- Handoff Package.

Persistence ownership applies only to Humanize downstream state.

It does not transfer ownership of upstream engagement truth.

## Source-of-truth boundary

Persistence must not become a shadow NEXUS system of record.

Humanize persistence must not independently reconstruct or maintain canonical
copies of:

- NEXUS engagement state;
- requirements;
- assumptions;
- constraints;
- architecture decisions;
- authoritative facts;
- evaluations;
- security decisions;
- upstream approval state;
- delivery readiness;
- authoritative NDEB schema;
- authoritative NDEB generation state.

Humanize must resolve upstream authority through an authorized exchange
boundary rather than direct internal coupling.

## Immutable upstream references

Where Humanize delivery state depends on upstream evidence, persistence should
prefer immutable authority references over duplicated source truth.

A stored reference must not acquire stronger authority merely because it is
durable.

A reference must not be silently rewritten to point to different upstream
authority.

The implementation representation of immutable references remains deferred.

## Approved downstream copies

The canonical V3 phase plan permits approved downstream copies only as later
authorized.

V3.2 does not grant that authorization.

A future approved downstream copy must, at minimum, preserve the authority
properties required by its later reviewed gate, including applicable:

- source identity;
- integrity binding;
- provenance;
- classification;
- tenant identity;
- engagement identity.

A downstream copy remains a downstream copy.

It must not become authoritative engagement truth.

## Existing backend model

The reviewed Humanize persistence substrate supports an architecture model
with:

- memory backend support;
- SQLite backend support;
- an external persistence configuration state;
- an external adapter that is explicitly not installed.

V3.2 architecture aligns with that substrate.

V3.2 does not install or activate another backend.

## Repository boundary

Future V3.2 implementation should preserve repository protocol boundaries
rather than couple domain services directly to a concrete storage engine.

Repository interfaces must preserve domain ownership and isolation rules.

A repository must not hide cross-tenant access behind a storage abstraction.

A repository must not treat persistence success as evidence-authority
validation.

Concrete repository interfaces remain implementation-phase work.

## Repository factory boundary

Existing Humanize repository-factory patterns may be reused when separately
authorized.

Backend selection must remain explicit and policy-controlled.

A factory must not silently downgrade required persistence guarantees.

A factory must not make an unavailable external adapter appear installed.

V3.2 does not modify the existing factory.

## Unit-of-work boundary

Existing Humanize unit-of-work architecture is an acceptable substrate for
future transactional composition.

Future client-delivery persistence may use a unit-of-work boundary when
multiple Humanize downstream records must change atomically.

A transaction boundary must not span into NEXUS internal persistence.

Humanize must not attempt distributed mutation of NEXUS state.

Exact transactional repositories and methods remain implementation-phase work.

## SQLite boundary

SQLite is an existing Humanize backend.

Its existence does not grant implicit production authority for V3.2.

A future V3.2 implementation may use SQLite only under the separately reviewed
runtime and deployment authority applicable to that implementation.

V3.2 architecture does not change current SQLite initialization.

V3.2 architecture does not add tables.

V3.2 architecture does not add indexes.

## External persistence boundary

The reviewed configuration contains an external persistence mode whose adapter
is not installed.

V3.2 must preserve that explicit non-installed posture.

A future external persistence adapter requires separate implementation,
security, configuration, operational, and acceptance authority.

Architecture planning must not claim such an adapter exists.

## Schema boundary

V3.2 architecture may define conceptual persistence ownership.

It must not define executable database schema.

Table names, columns, data types, foreign keys, uniqueness constraints,
indexes, physical partitioning, and storage-specific DDL are implementation
concerns.

No database-schema mutation is authorized in V3.2 architecture planning.

## Migration boundary

The reviewed repository does not establish a migration-framework directory or
Alembic-style migration framework.

Several tests use the word migration to validate behavioral compatibility and
historical storage evolution.

Those test filenames do not establish a database migration framework.

V3.2 must not invent or select a migration framework during architecture
package creation.

Any future migration mechanism requires separately reviewed implementation
authority.

## Tenant isolation

Persistence must enforce the architecture invariant that Humanize
client-delivery state belongs to the correct tenant.

Storage lookup convenience must never replace tenant authorization.

Cross-tenant queries and writes must fail closed unless a future reviewed
contract explicitly authorizes a reusable cross-tenant artifact class.

## Engagement binding

Engagement-specific delivery records must preserve their engagement binding.

A database record must not become reusable across engagements merely because a
storage key is known.

Persistence design must support deterministic rejection of mismatched
engagement context when later runtime behavior is implemented.

## Classification preservation

Persistence of classified downstream state must not weaken source
classification.

Storage backends must not silently omit required classification bindings.

Encryption, storage-class controls, retention rules, and deployment-specific
security mechanisms remain future implementation and operational concerns.

## Provenance preservation

Persistence must retain the source-authority linkage required by governed
delivery workflows.

A local database identifier alone is insufficient provenance.

Persistence must not replace source provenance with presentation narrative.

## Approval records

Persistence may eventually store Humanize-side Approval Records.

Storing an Approval Record does not authorize approval.

Exact approval semantics remain V3.6 responsibilities.

Upstream approval state remains upstream authority.

## Export authorization records

Persistence may eventually store Humanize-side Export Authorization Records.

Storing an export record does not authorize export.

Exact export decision and manifest semantics remain V3.7 responsibilities.

## Artifact and package records

Persistence may eventually store Humanize metadata for Delivery Artifacts and
Handoff Packages.

Persistence does not authorize generation.

DOCX and PDF generation remain V3.8 responsibilities.

PPTX generation remains V3.9 responsibility.

Complete handoff-package assembly remains V3.10 responsibility.

## Failure posture

Future persistence implementation must fail closed when required authority
cannot be established.

Examples include:

- unknown tenant;
- engagement mismatch;
- foreign-tenant source reference;
- missing required source-authority reference;
- unverifiable integrity where integrity is required;
- missing required classification;
- ambiguous ownership;
- unsupported persistence backend;
- unavailable configured adapter.

Exact runtime failure types are not defined in V3.2 architecture.

## Explicit non-authority

`PERSISTENCE_IMPLEMENTATION_AUTHORITY = NONE`

`DATABASE_SCHEMA_AUTHORITY = NONE`

`MIGRATION_AUTHORITY = NONE`

`EXTERNAL_PERSISTENCE_ADAPTER_AUTHORITY = NONE`

`NDEB_INGESTION_RUNTIME_AUTHORITY = NONE`

`V3_2_IMPLEMENTATION_AUTHORITY = NONE`

## Final invariant

Humanize persistence exists to durably govern Humanize downstream delivery
state.

It must never become a second authoritative store for NEXUS engagement truth.
