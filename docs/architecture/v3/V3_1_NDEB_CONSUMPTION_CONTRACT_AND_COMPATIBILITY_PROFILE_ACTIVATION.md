# Humanize V3.1 NDEB Consumption Contract and Compatibility Profile Activation

## Status

V3.1 architecture-package candidate.

This document authorizes architecture planning only.

It does not grant runtime implementation authority.

It does not define the authoritative NEXUS Delivery Evidence Bundle schema.

## Canonical predecessor

V3.1 begins from the canonically closed Humanize V3.0 baseline:

```text
HUMANIZE_V3_0_CANONICAL_MAIN =
012fa76769d1dd06771ab306de8416d668efb9c3

HUMANIZE_V3_0_CANONICAL_TREE =
e31d7e12a1f219c2842d7ba1677b4d0b0166a10a
```

V3.0 remains closed.

## Purpose

V3.1 defines the Humanize consumer-side contract and compatibility policy for
a future canonical NEXUS Delivery Evidence Bundle.

V3.1 answers:

- what upstream schema identity Humanize is bound to;
- which upstream schema versions Humanize explicitly supports;
- what integrity evidence Humanize requires;
- what tenant and engagement identity requirements apply;
- what provenance and classification requirements apply;
- how compatibility is determined;
- when consumption must fail closed;
- what future compatibility fixtures must prove.

V3.1 does not define upstream truth.

## Authority model

NEXUS owns:

- authoritative engagement truth;
- authoritative NDEB schema definition;
- authoritative NDEB schema versioning;
- deterministic authoritative NDEB generation;
- NEXUS persistence;
- NEXUS source-of-truth semantics.

Humanize V3.1 may own:

- consumer-side binding requirements;
- supported-version declarations after an upstream schema exists;
- consumer compatibility policy;
- consumer rejection requirements;
- future compatibility-fixture requirements.

Humanize must not define the authoritative NDEB schema.

Humanize must not generate authoritative NDEB artifacts.

## Upstream authority references

The currently reviewed authority-bearing NEXUS architecture artifacts are:

```text
CLIENT_DELIVERY_EVIDENCE_EXCHANGE_CONTRACT_BLOB =
31d7d709d9092b79d1e26ce1b5acfef634bd49e6

ADR_0006_CLIENT_DELIVERY_EVIDENCE_EXCHANGE_BOUNDARY_BLOB =
81ff9d9ad467a9bd8ccc0e892fc5587668b383fc
```

These artifacts establish ownership and future interoperability direction.

They are not a canonical executable NDEB schema.

## Current compatibility binding posture

At V3.1 activation:

```text
V3_1_COMPATIBILITY_PROFILE_BINDING_STATE =
UNBOUND_PENDING_CANONICAL_NEXUS_SCHEMA

V3_1_SUPPORTED_UPSTREAM_SCHEMA_IDENTITY =
NONE_CURRENTLY

V3_1_SUPPORTED_UPSTREAM_SCHEMA_VERSION =
NONE_CURRENTLY
```

Humanize must not invent a schema identity or version to remove this unbound
state.

Unbound consumption fails closed.

## V3.1 may define

V3.1 may define consumer requirements for:

- supported upstream schema identity;
- supported upstream schema versions;
- required integrity metadata;
- required tenant identity;
- required engagement identity;
- required provenance metadata;
- required classification metadata;
- compatibility rules;
- consumer rejection semantics;
- compatibility fixture requirements.

## V3.1 must not define

V3.1 must not define:

- authoritative NDEB wire fields;
- authoritative NDEB field names;
- authoritative NDEB field types;
- authoritative NDEB enums;
- authoritative NDEB schema version values;
- authoritative NDEB generation;
- NEXUS internal persistence;
- NEXUS source-of-truth semantics.

Consumer requirements must not become an upstream schema by implication.

## Live adapter interlock

Live NDEB adapter implementation remains blocked.

A live adapter requires, at minimum:

1. a canonical NEXUS exchange schema;
2. an explicit Humanize compatibility binding to that schema;
3. separately authorized compatibility fixtures;
4. separately authorized consumer validation;
5. security review;
6. provenance validation;
7. the separately authorized implementation gate.

V3.1 architecture planning satisfies none of those runtime authorities.

## Fixture separation

V3.1 may document what future compatibility fixtures must prove.

V3.1 does not authorize:

- fixture files;
- fixture generators;
- fixture test code;
- schema-validator code;
- adapter runtime;
- ingestion runtime.

## Architecture package

The V3.1 candidate package contains exactly:

```text
docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT_AND_COMPATIBILITY_PROFILE_ACTIVATION.md
docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT.md
docs/architecture/v3/V3_1_NDEB_COMPATIBILITY_PROFILE.md
docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT_AND_COMPATIBILITY_PROFILE_ACCEPTANCE_CRITERIA.md
```

No application source, tests, fixtures, persistence, UI, runtime adapter, or
export implementation belongs to this package.

## Explicit non-authority

```text
V3_1_IMPLEMENTATION_AUTHORITY = NONE
NDEB_SCHEMA_DEFINITION_AUTHORITY = NONE
NDEB_GENERATION_AUTHORITY = NONE
NEXUS_ADAPTER_IMPLEMENTATION_AUTHORITY = NONE
COMPATIBILITY_FIXTURE_IMPLEMENTATION_AUTHORITY = NONE
CLIENT_DELIVERY_UI_AUTHORITY = NONE
CLIENT_DELIVERY_PERSISTENCE_AUTHORITY = NONE
EXPORT_GENERATION_AUTHORITY = NONE
```

## Closure posture

The V3.1 package remains candidate architecture until separately reviewed,
committed, accepted, merged to canonical `main`, and post-merge verified.

Canonicalization of V3.1 does not itself bind Humanize to a future schema.

A later compatibility-profile binding change requires its own reviewed
authority after NEXUS publishes a canonical exchange schema.

## Final invariant

Humanize may define what it requires as a consumer.

Humanize may not manufacture the upstream contract it intends to consume.
