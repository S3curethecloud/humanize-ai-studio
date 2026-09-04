# Humanize V3.1 NDEB Consumption Contract and Compatibility Profile Acceptance Criteria

## Status

V3.1 architecture acceptance candidate.

These criteria govern acceptance of the V3.1 architecture package.

They do not grant runtime implementation authority.

## A. Canonical predecessor

Acceptance requires:

- Humanize V3.0 remains canonically closed;
- V3.1 begins from canonical Humanize main
  `012fa76769d1dd06771ab306de8416d668efb9c3`;
- no earlier V3.0 authority boundary is weakened.

## B. Exact package boundary

The V3.1 package contains exactly:

```text
docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT_AND_COMPATIBILITY_PROFILE_ACTIVATION.md
docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT.md
docs/architecture/v3/V3_1_NDEB_COMPATIBILITY_PROFILE.md
docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT_AND_COMPATIBILITY_PROFILE_ACCEPTANCE_CRITERIA.md
```

Acceptance fails if the package introduces application source, tests, fixture
files, runtime configuration, persistence, UI, or generated delivery
artifacts.

## C. Consumer-side purpose

Acceptance requires V3.1 to remain a Humanize consumer-side compatibility
architecture phase.

V3.1 may define requirements for:

- upstream schema identity;
- upstream schema version support;
- integrity;
- tenant identity;
- engagement identity;
- provenance;
- classification;
- compatibility;
- consumer rejection;
- future compatibility fixtures.

## D. Upstream ownership

Acceptance requires:

- authoritative NDEB schema definition remains NEXUS-owned;
- authoritative NDEB version semantics remain NEXUS-owned;
- authoritative NDEB generation remains NEXUS-owned;
- NEXUS persistence remains NEXUS-owned;
- NEXUS source-of-truth semantics remain NEXUS-owned.

Humanize must not convert its consumer contract into an upstream schema.

## E. Current compatibility binding

Acceptance requires the initial V3.1 compatibility profile to remain:

```text
V3_1_COMPATIBILITY_PROFILE_BINDING_STATE =
UNBOUND_PENDING_CANONICAL_NEXUS_SCHEMA

V3_1_SUPPORTED_UPSTREAM_SCHEMA_IDENTITY =
NONE_CURRENTLY

V3_1_SUPPORTED_UPSTREAM_SCHEMA_VERSION =
NONE_CURRENTLY
```

Consumption while unbound must fail closed.

## F. No invented upstream schema

Acceptance fails if V3.1 invents or canonically claims:

- authoritative wire field names;
- authoritative wire field types;
- authoritative wire enums;
- an upstream schema identifier;
- an upstream schema version;
- serialization rules;
- generation rules;
- upstream compatibility semantics that NEXUS has not defined.

## G. Consumer contract requirements

Acceptance requires the consumer contract to address:

- explicit upstream binding;
- schema identity;
- schema version;
- integrity;
- tenant identity;
- engagement identity;
- provenance;
- classification;
- deterministic compatibility;
- fail-closed rejection.

The contract must distinguish consumer requirements from upstream wire
semantics.

## H. Rejection posture

Acceptance requires fail-closed behavior when required compatibility authority
cannot be established.

At minimum, the architecture must require rejection for:

- unbound profile;
- unsupported schema identity;
- unsupported schema version;
- invalid or unverifiable integrity;
- tenant mismatch;
- engagement mismatch;
- insufficient required provenance;
- absent or unsupported required classification;
- ambiguous compatibility semantics.

## I. Read-only boundary

Acceptance requires NDEB consumption to remain read-only.

Humanize must not:

- mutate NEXUS state;
- modify upstream evidence;
- change architecture decisions;
- change evaluation outcomes;
- convert assumptions into facts;
- weaken classification;
- remove provenance;
- generate authoritative NDEB artifacts.

## J. Compatibility-profile policy

Acceptance requires:

- supported identities are explicit;
- supported versions are explicit;
- no forward compatibility is assumed;
- no backward compatibility is assumed;
- no semantic-version compatibility is assumed without upstream authority;
- unknown extensions fail closed unless explicitly permitted;
- NEXUS `main` advancement alone does not change Humanize compatibility.

## K. Fixture separation

V3.1 may define compatibility-fixture requirements.

V3.1 does not authorize:

- compatibility fixture files;
- test implementations;
- fixture generators;
- validator implementations;
- fixture execution;
- consumer runtime validation.

Future fixtures require separate authority.

## L. Live adapter interlock

Acceptance requires:

```text
LIVE_NDEB_ADAPTER_STATUS = BLOCKED
NDEB_INGESTION_RUNTIME_STATUS = BLOCKED
NDEB_SCHEMA_VALIDATOR_RUNTIME_STATUS = BLOCKED
```

A canonical NEXUS exchange schema and separately reviewed Humanize binding are
prerequisites, not runtime authorization.

## M. Runtime non-authority

Acceptance requires:

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

## N. Presentation-authority non-escalation

Compatibility acceptance must not make Humanize an evidence authority.

NEXUS determines truth.

Humanize determines downstream compatibility and presentation.

Presentation never becomes evidence authority.

## O. Runtime independence

Acceptance requires NEXUS to remain independently operable without Humanize.

Humanize must not become required for NEXUS evidence generation, evidence
export, or baseline deterministic client delivery.

## P. V3.1 canonicalization

V3.1 may become canonical while its compatibility profile remains unbound.

Canonicalization means the Humanize consumer policy is accepted.

It does not mean an upstream NDEB schema exists.

It does not mean Humanize supports a live NDEB version.

A later binding to a canonical NEXUS schema requires separate reviewed
authority.

## Q. Closure sequence

V3.1 may be declared canonically closed only after:

1. exact four-document package creation;
2. package creation review;
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

```text
V3_1_STATUS = CANDIDATE
V3_1_IMPLEMENTATION_AUTHORITY = NONE
```

## Failure posture

Acceptance fails if V3.1:

- defines the authoritative NDEB schema;
- invents an upstream schema identity or version;
- grants NDEB generation authority to Humanize;
- grants live adapter authority;
- grants ingestion runtime authority;
- creates fixture implementations;
- weakens tenant isolation;
- weakens provenance;
- weakens classification;
- makes Humanize a source of engagement truth;
- makes Humanize a required NEXUS runtime dependency.

## Final acceptance invariant

V3.1 succeeds when Humanize has a precise, fail-closed consumer compatibility
contract without claiming upstream schema authority or prematurely enabling
runtime integration.
