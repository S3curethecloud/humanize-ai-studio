# Humanize V3.1 NDEB Consumption Contract

## Status

Consumer-side architecture contract candidate.

No runtime implementation is authorized.

This contract does not define the authoritative NDEB wire schema.

## Purpose

Define the conditions under which Humanize may eventually accept a canonical
NEXUS Delivery Evidence Bundle for downstream client-delivery workflows.

The contract governs Humanize consumption behavior.

It does not govern NEXUS generation behavior.

## Authority boundary

NEXUS remains authoritative for:

- engagement truth;
- NDEB schema identity;
- NDEB schema versioning;
- NDEB schema semantics;
- NDEB generation;
- evidence approval;
- provenance authority.

Humanize remains a downstream consumer.

Humanize must not reinterpret consumer expectations as upstream truth.

## Current binding state

```text
COMPATIBILITY_PROFILE_BINDING_STATE =
UNBOUND_PENDING_CANONICAL_NEXUS_SCHEMA

SUPPORTED_UPSTREAM_SCHEMA_IDENTITY =
NONE_CURRENTLY

SUPPORTED_UPSTREAM_SCHEMA_VERSION =
NONE_CURRENTLY
```

Consumption fails closed while the compatibility profile is unbound.

## Consumer binding requirement

Before Humanize may treat an NDEB as compatible, the compatibility profile must
identify an upstream schema that is:

- canonical in NEXUS;
- explicitly identified;
- explicitly versioned by NEXUS;
- covered by a separately reviewed Humanize compatibility binding.

Humanize must not infer an identity from filenames, repository paths, prose,
payload shape, field coincidence, or generated narrative.

Humanize must not infer a version from chronology, commit order, semantic
version conventions, or a value Humanize invents.

## Required semantic compatibility categories

A future supported NDEB must provide canonical upstream semantics sufficient
for Humanize to validate the following categories.

### Schema identity

Humanize requires an authoritative upstream schema identity that can be bound
to the compatibility profile.

V3.1 does not specify the wire field that carries that identity.

### Schema version

Humanize requires an authoritative upstream schema version that is explicitly
listed as supported by the compatibility profile.

V3.1 does not specify the wire representation or version syntax.

### Integrity

Humanize requires verifiable integrity metadata sufficient to establish that
the consumed bundle has not drifted from the authoritative exported artifact.

The integrity algorithm, encoding, and wire representation remain upstream
schema concerns unless separately governed elsewhere.

### Tenant identity

Humanize requires sufficient authoritative tenant identity to prevent
cross-tenant consumption.

The authoritative wire field and representation remain upstream concerns.

### Engagement identity

Humanize requires sufficient authoritative engagement identity to bind the
bundle to the intended client-delivery context.

The authoritative wire field and representation remain upstream concerns.

### Provenance

Humanize requires provenance sufficient to preserve traceability from material
downstream claims to authoritative source evidence.

The authoritative provenance representation remains upstream-owned.

### Classification

Humanize requires classification metadata sufficient to preserve or strengthen
handling controls.

Humanize must never silently weaken upstream classification.

The authoritative classification representation remains upstream-owned.

## Compatibility decision requirements

A future consumer compatibility decision must be deterministic for the same:

- canonical upstream schema identity;
- canonical upstream schema version;
- compatibility-profile revision;
- required integrity evidence;
- tenant context;
- engagement context;
- provenance requirements;
- classification requirements.

Compatibility must never depend on narrative plausibility.

## Fail-closed rejection requirements

Humanize must reject consumption when any required condition cannot be
authoritatively established.

Conceptual rejection classes include:

- compatibility profile unbound;
- unsupported schema identity;
- unsupported schema version;
- unverifiable or invalid integrity;
- invalid or mismatched tenant identity;
- invalid or mismatched engagement identity;
- insufficient required provenance;
- absent or unsupported required classification;
- ambiguous upstream compatibility semantics;
- authority-boundary violation.

These are consumer-side conceptual rejection classes.

They are not authoritative upstream wire enums or API constants.

## Unsupported and unknown upstream content

Humanize must not assume that unknown upstream content is safe.

Unknown fields, extensions, versions, or structures may be accepted only when
the canonical upstream schema and the reviewed compatibility profile explicitly
permit that behavior.

Absent such authority, consumption fails closed.

## Read-only consumption

NDEB consumption is read-only.

Humanize consumption must not:

- modify NEXUS state;
- write back to NEXUS evidence;
- change architecture decisions;
- change evaluation outcomes;
- upgrade assumptions into facts;
- weaken classification;
- remove provenance;
- generate an authoritative NDEB.

## Presentation authority

Successful compatibility does not transform Humanize output into evidence
authority.

Compatibility means only that an upstream artifact satisfies the reviewed
consumer requirements.

Presentation remains downstream of evidence authority.

## Future compatibility-fixture requirements

Future fixtures, when separately authorized, must prove at least:

- acceptance of an explicitly supported canonical schema identity;
- acceptance of an explicitly supported canonical schema version;
- rejection while the profile is unbound;
- rejection of an unsupported schema identity;
- rejection of an unsupported schema version;
- rejection of invalid or unverifiable integrity;
- rejection of tenant mismatch;
- rejection of engagement mismatch;
- rejection of insufficient required provenance;
- rejection of absent or unsupported required classification;
- deterministic behavior for identical compatibility inputs.

V3.1 defines these fixture requirements only.

V3.1 does not authorize fixture files or fixture execution.

## Runtime independence

NEXUS must remain independently operable without Humanize.

Humanize must not become required for NEXUS evidence creation, export, or
baseline deterministic delivery.

## Implementation posture

```text
NEXUS_ADAPTER_IMPLEMENTATION_AUTHORITY = NONE
NDEB_INGESTION_RUNTIME_AUTHORITY = NONE
NDEB_SCHEMA_VALIDATOR_RUNTIME_AUTHORITY = NONE
COMPATIBILITY_FIXTURE_IMPLEMENTATION_AUTHORITY = NONE
```

## Final invariant

Humanize accepts only explicitly bound, supported, authoritative upstream
evidence.

When compatibility authority is incomplete, Humanize rejects rather than
guesses.
