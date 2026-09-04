# Humanize V3.1 NDEB Compatibility Profile

## Status

Consumer compatibility-profile candidate.

The profile is currently unbound.

No live NDEB schema is supported by Humanize at this time.

## Purpose

Define how Humanize records and evaluates compatibility with canonical NEXUS
Delivery Evidence Bundle schemas after those schemas are actually published by
NEXUS.

The profile does not define an upstream schema.

## Current profile

```text
V3_1_COMPATIBILITY_PROFILE_BINDING_STATE =
UNBOUND_PENDING_CANONICAL_NEXUS_SCHEMA

V3_1_SUPPORTED_UPSTREAM_SCHEMA_IDENTITY =
NONE_CURRENTLY

V3_1_SUPPORTED_UPSTREAM_SCHEMA_VERSION =
NONE_CURRENTLY

V3_1_UNBOUND_SCHEMA_CONSUMPTION_POSTURE =
FAIL_CLOSED
```

This state is intentional.

It must not be removed by inventing an upstream identity or version.

## Binding authority

A future profile binding may be established only after NEXUS has canonically
published the exchange schema being consumed.

A binding decision must be separately reviewed by Humanize.

A future binding record must preserve enough authority evidence to identify:

- the authoritative NEXUS source;
- the canonical NEXUS revision containing the schema;
- the canonical schema identity as defined by NEXUS;
- the canonical schema version as defined by NEXUS;
- the reviewed Humanize compatibility disposition;
- the evidence supporting that disposition.

The profile must reference upstream authority.

It must not copy consumer assumptions into upstream authority.

## Schema identity policy

Humanize may explicitly support a canonical upstream schema identity only after
that identity exists in NEXUS authority.

Humanize must not:

- invent a schema identity;
- alias an unofficial identity into canonical status;
- derive identity from a filename;
- derive identity from payload shape;
- derive identity from prose similarity.

## Version support policy

Humanize may explicitly support upstream versions only after NEXUS defines
those versions canonically.

No version is supported merely because it is:

- newer;
- older;
- numerically adjacent;
- chronologically recent;
- semantically similar;
- labeled with a familiar versioning convention.

Humanize does not assume semantic-version compatibility unless the canonical
upstream contract explicitly establishes such semantics and Humanize
separately reviews the resulting compatibility rule.

Each supported version must be explicitly bound.

## Consumer compatibility dimensions

A future bound profile must evaluate consumer requirements for:

- upstream schema identity;
- upstream schema version;
- integrity;
- tenant identity;
- engagement identity;
- provenance;
- classification;
- deterministic rejection behavior.

These dimensions describe Humanize compatibility expectations.

They do not define upstream wire fields, types, enums, or serialization.

## Compatibility posture

The profile supports three architecture-level dispositions:

### Unbound

No canonical upstream schema is bound.

Consumption is prohibited.

### Supported

A canonical upstream schema identity and version have been explicitly reviewed
and bound for Humanize consumption.

A supported disposition alone does not grant runtime adapter authority.

### Unsupported

The reviewed upstream identity or version is not accepted for Humanize
consumption.

These dispositions are compatibility-policy concepts.

They are not authoritative NDEB wire enums.

## Forward and backward compatibility

Humanize assumes no forward compatibility.

Humanize assumes no backward compatibility.

Humanize assumes no cross-version compatibility.

Any compatibility across upstream versions must be explicitly justified by
canonical NEXUS schema governance and separately accepted in the Humanize
profile.

## Unknown extensions

Unknown upstream extensions are not automatically compatible.

They may be tolerated only when canonical NEXUS schema rules explicitly permit
the extension and the Humanize compatibility binding accepts that behavior.

Otherwise, consumption fails closed.

## Future fixture matrix

When fixture implementation is separately authorized, the fixture set must
include positive and negative evidence for the bound profile.

Required categories include:

- supported schema identity;
- supported schema version;
- unbound profile;
- unsupported identity;
- unsupported version;
- integrity failure;
- tenant mismatch;
- engagement mismatch;
- provenance insufficiency;
- classification failure;
- deterministic repeatability.

No fixture file is authorized by this profile.

## Change control

A change to any supported upstream identity or version requires a separately
reviewed compatibility-profile change.

NEXUS `main` advancing does not automatically change Humanize compatibility.

Humanize compatibility changes only when relevant upstream schema authority
changes and Humanize explicitly accepts the new binding.

## Live adapter interlock

```text
LIVE_NDEB_ADAPTER_STATUS = BLOCKED
NDEB_INGESTION_RUNTIME_STATUS = BLOCKED
NDEB_SCHEMA_VALIDATOR_RUNTIME_STATUS = BLOCKED
```

A bound compatibility profile is necessary but not sufficient for runtime
implementation.

Separate implementation authority remains mandatory.

## Authority freeze

```text
NDEB_SCHEMA_DEFINITION_AUTHORITY = NONE
NDEB_GENERATION_AUTHORITY = NONE
NEXUS_ADAPTER_IMPLEMENTATION_AUTHORITY = NONE
COMPATIBILITY_FIXTURE_IMPLEMENTATION_AUTHORITY = NONE
V3_1_IMPLEMENTATION_AUTHORITY = NONE
```

## Final invariant

The compatibility profile records what Humanize has explicitly accepted from
canonical upstream authority.

It never creates that upstream authority.
