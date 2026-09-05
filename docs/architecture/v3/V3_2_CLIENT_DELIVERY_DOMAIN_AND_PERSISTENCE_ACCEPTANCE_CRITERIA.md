# Humanize V3.2 Client Delivery Domain and Persistence Acceptance Criteria

## Status

V3.2 architecture acceptance candidate.

These criteria govern acceptance of the V3.2 architecture package.

They do not grant runtime implementation authority.

## A. Canonical predecessor

Acceptance requires:

- V3.0 remains canonically closed;
- V3.1 remains canonically closed;
- V3.2 begins from canonical Humanize main
  `e23d009b5a119f42f1deb04b55c1913ec174073a`;
- the canonical predecessor tree is
  `b87bf51c928dffa6d4f652b604adba61b2f889bc`;
- no V3.0 or V3.1 authority boundary is weakened.

## B. Exact architecture package

The V3.2 package contains exactly:

- `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_AND_PERSISTENCE_ACTIVATION.md`
- `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_MODEL.md`
- `docs/architecture/v3/V3_2_CLIENT_DELIVERY_PERSISTENCE_ARCHITECTURE.md`
- `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_AND_PERSISTENCE_ACCEPTANCE_CRITERIA.md`

Acceptance fails if package creation introduces application source, tests,
database schema, migrations, runtime configuration, APIs, UI, fixtures,
generated client files, adapters, or executable persistence implementation.

## C. V3.2 purpose

Acceptance requires V3.2 to remain a Humanize downstream domain and
persistence architecture phase.

Its purpose is to define Humanize-owned client-delivery state without
acquiring ownership of upstream engagement truth.

## D. Exact domain-area coverage

Acceptance requires architecture coverage for all nine V3.2 domain areas:

1. Delivery Workspace
2. Imported Bundle Reference
3. Delivery Artifact
4. Protected Delivery Fact
5. Source Evidence Reference
6. Approval Record
7. Export Authorization Record
8. Delivery Manifest
9. Handoff Package

Acceptance fails if architecture silently removes a required area.

Acceptance also fails if V3.2 uses those domain areas to pre-authorize later
runtime phases.

## E. Upstream authority boundary

Acceptance requires NEXUS to remain authoritative for upstream engagement
truth.

Humanize must not redefine or duplicate authoritative:

- engagement state;
- requirements;
- assumptions;
- constraints;
- architecture decisions;
- facts;
- evidence;
- evaluations;
- security decisions;
- upstream approvals;
- delivery readiness;
- NDEB schema;
- NDEB version semantics;
- NDEB generation.

Persistence must not become a shadow NEXUS system of record.

## F. V3.1 compatibility interlock

Acceptance requires the canonical V3.1 state to remain:

`V3_1_COMPATIBILITY_PROFILE_BINDING_STATE = UNBOUND_PENDING_CANONICAL_NEXUS_SCHEMA`

`V3_1_SUPPORTED_UPSTREAM_SCHEMA_IDENTITY = NONE_CURRENTLY`

`V3_1_SUPPORTED_UPSTREAM_SCHEMA_VERSION = NONE_CURRENTLY`

V3.2 must not bind a schema.

V3.2 must not invent schema identity or version.

Live NDEB adapter and ingestion runtime remain blocked.

## G. Domain identity

Acceptance requires the domain architecture to establish:

- tenant identity as an isolation boundary;
- engagement binding for engagement-specific delivery state;
- stable Humanize-side object identity;
- source-authority references where required.

Humanize object identity must not replace upstream source identity.

## H. Tenant isolation

Acceptance requires every client-delivery aggregate to preserve the correct
tenant boundary.

Cross-tenant reuse must fail closed unless a future explicitly reviewed
contract defines a safe reusable-artifact class.

Structural similarity must not establish tenant authority.

## I. Engagement isolation

Acceptance requires engagement-specific delivery state to remain bound to the
correct engagement.

Presentation similarity, filenames, local paths, or object shape must not
establish engagement equivalence.

## J. Source-reference semantics

Acceptance requires upstream references to remain authority references.

Humanize must not derive upstream authority from:

- local filenames;
- local database identifiers;
- payload similarity;
- prose similarity;
- chronology;
- presentation content.

V3.2 must not define NDEB wire fields.

## K. Protected delivery facts

Acceptance requires Protected Delivery Fact architecture to preserve source
authority.

A protected fact must not:

- convert assumptions into facts;
- change architecture decisions;
- change evaluation outcomes;
- remove provenance;
- weaken classification;
- create new upstream approval.

Exact protection behavior remains V3.4 responsibility.

## L. Approval and export separation

Acceptance requires Humanize Approval Records to remain distinct from upstream
approval authority.

Exact approval lifecycle semantics remain V3.6 responsibility.

Acceptance requires Export Authorization Records to remain distinct from
artifact-generation authority.

Exact manifest and export semantics remain V3.7 responsibility.

Generation alone must not imply export authority.

## M. Persistence ownership

Acceptance requires persistence ownership to be limited to Humanize downstream
delivery state.

Humanize persistence may preserve immutable upstream references.

Approved downstream copies remain separately authorized future capability.

A downstream copy must not become upstream truth.

## N. Existing persistence substrate compatibility

Acceptance requires the architecture to remain compatible with the reviewed
Humanize substrate:

- memory backend;
- SQLite backend;
- explicit external-backend configuration;
- external adapter not installed;
- repository protocol boundaries;
- repository factories;
- unit-of-work architecture;
- existing SQLite initialization patterns.

V3.2 architecture must not mutate that substrate.

## O. Repository and unit-of-work boundary

Acceptance requires future persistence implementation to use explicit
repository boundaries rather than direct storage coupling where repository
abstractions are applicable.

Future transaction boundaries must remain inside Humanize persistence.

Humanize must not establish a transaction that mutates NEXUS internal state.

## P. Backend authority

Acceptance requires backend selection to remain explicit.

SQLite support must not become implicit V3.2 production authority.

An unavailable external adapter must not be represented as installed.

Any future external adapter requires separate reviewed authority.

## Q. Database schema and migration boundary

Acceptance requires:

`DATABASE_SCHEMA_AUTHORITY = NONE`

`MIGRATION_AUTHORITY = NONE`

The V3.2 architecture package must not create:

- tables;
- columns;
- indexes;
- foreign keys;
- DDL;
- migration scripts;
- migration framework configuration.

The presence of test filenames containing the word migration does not establish
a migration framework.

## R. Classification and provenance

Acceptance requires persistence and domain architecture to preserve applicable
classification and provenance boundaries.

Humanize may later strengthen handling.

Humanize must not silently weaken classification.

Local persistence identifiers must not replace required source provenance.

## S. Later-phase reservations

Acceptance requires the following behavior to remain outside V3.2:

- V3.3: bundle ingestion and validation;
- V3.4: provenance, claim protection, and classification runtime behavior;
- V3.5: governed composition;
- V3.6: human approval lifecycle;
- V3.7: manifest and export authorization;
- V3.8: DOCX and PDF generation;
- V3.9: PPTX and executive presentation generation;
- V3.10: complete handoff-package assembly.

V3.2 must not preempt later-phase implementation authority.

## T. Runtime non-authority

Acceptance requires:

`V3_2_IMPLEMENTATION_AUTHORITY = NONE`

`DOMAIN_MODEL_IMPLEMENTATION_AUTHORITY = NONE`

`PERSISTENCE_IMPLEMENTATION_AUTHORITY = NONE`

`DATABASE_SCHEMA_AUTHORITY = NONE`

`MIGRATION_AUTHORITY = NONE`

`NDEB_SCHEMA_DEFINITION_AUTHORITY = NONE`

`NDEB_GENERATION_AUTHORITY = NONE`

`NDEB_BINDING_AUTHORITY = NONE`

`NDEB_INGESTION_RUNTIME_AUTHORITY = NONE`

`CLIENT_DELIVERY_API_AUTHORITY = NONE`

`CLIENT_DELIVERY_UI_AUTHORITY = NONE`

`EXPORT_GENERATION_AUTHORITY = NONE`

## U. Presentation-authority non-escalation

Acceptance requires persisted Humanize delivery state to remain downstream
presentation and delivery state.

Persistence success must not convert presentation into evidence authority.

NEXUS determines upstream truth.

Humanize governs downstream delivery state.

## V. Closure sequence

V3.2 may be declared canonically closed only after:

1. exact four-document architecture package creation;
2. architecture package creation review;
3. semantic and boundary acceptance;
4. bounded staging and commit;
5. commit acceptance review;
6. bounded push;
7. push acceptance review;
8. pull-request creation;
9. pull-request acceptance;
10. canonical merge;
11. post-merge verification.

Until closure:

`V3_2_STATUS = CANDIDATE`

`V3_2_IMPLEMENTATION_AUTHORITY = NONE`

## Failure posture

Acceptance fails if V3.2:

- makes Humanize authoritative for engagement truth;
- creates or implies a shadow NEXUS system of record;
- invents NDEB schema identity or version;
- grants NDEB ingestion authority;
- creates executable domain models;
- creates persistence runtime;
- creates database schema;
- creates migrations;
- claims an external adapter is installed;
- weakens tenant isolation;
- weakens engagement binding;
- weakens provenance;
- weakens classification;
- preempts V3.3 through V3.10 runtime semantics.

## Final acceptance invariant

V3.2 succeeds when Humanize has a precise downstream domain and persistence
architecture that is durable enough for later implementation while remaining
strictly subordinate to upstream NEXUS truth authority.
