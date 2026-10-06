# Humanize V3.3 NDEB Bundle Ingestion and Validation Activation

## Status

```text
V3_3_ARCHITECTURE_PACKAGE_STATUS=NONCANONICAL_CANDIDATE
V3_3_PHASE=Bundle Ingestion and Validation
V3_3_ACTIVATION_AUTHORITY=ARCHITECTURE_PACKAGE_PREPARATION_ONLY
V3_3_IMPLEMENTATION_AUTHORITY=NONE
```

This document is a V3.3 architecture-activation candidate.

It does not authorize runtime implementation.

It does not activate a live NEXUS adapter, NDEB ingestion runtime, schema
validator runtime, API route, persistence implementation, dependency
installation, deployment, export, or client release.

The candidate becomes architecture authority only through its own separately
governed repository materialization, staging, commit, publication,
pull-request, merge, and post-merge canonical acceptance lifecycle.

## Purpose

Activate bounded architecture planning for the Humanize read-only NEXUS
Delivery Evidence Bundle consumption boundary.

V3.3 exists to define how Humanize may receive an already-authorized NDEB
artifact, validate it deterministically against the supported canonical
upstream contract, and fail closed before any downstream Humanize delivery
workflow may rely on that bundle.

V3.3 does not make Humanize an upstream evidence authority.

## Canonical Humanize baseline

```text
HUMANIZE_CANONICAL_MAIN=
ae40c2a84ba7d41c36b56f3512c4a80b7ff2dd6e

HUMANIZE_CANONICAL_TREE=
330e6e5d56f687b2bef4c60dc8aafd0839891ab9

V3_1_BINDING_EFFECTIVE=
YES

V3_1_COMPATIBILITY_PROFILE_BINDING_STATE=
SUPPORTED

V3_1_SUPPORTED_UPSTREAM_SCHEMA_IDENTITY=
urn:nexus:ndeb

V3_1_SUPPORTED_UPSTREAM_SCHEMA_VERSION=
1.0.0

V3_1_SUPPORTED_UPSTREAM_SCHEMA_DOCUMENT_ID=
urn:nexus:ndeb:schema:1.0.0
```

The original V3.1 source documents that record an earlier unbound state remain
immutable historical lifecycle evidence.

The effective supported state is established by the later canonical V3.1
binding record and its accepted post-merge governance lifecycle.

## Canonical Humanize source locks

The V3.3 candidate is derived from these exact Humanize source objects:

| Source | Git blob |
| --- | --- |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_ACTIVATION.md` | `db264b0ac637063943145c8e8dd465c5a9208342` |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_SYSTEM_BOUNDARY.md` | `01121fee2a60bb675a9ad82b4040da85b9a5ae75` |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_PHASE_PLAN.md` | `92b506c7e1d06a229f6669defa29b8eab8106eb0` |
| `docs/architecture/v3/V3_CLIENT_DELIVERY_ACCEPTANCE_CRITERIA.md` | `5681e17207987b5fcfe8f360c4f403394db06f04` |
| `docs/architecture/v3/V3_1_NDEB_CONSUMPTION_CONTRACT.md` | `29daa3eb543e0529cd41fe2b8bad0fb9b3e1109f` |
| `docs/architecture/v3/V3_1_NDEB_COMPATIBILITY_PROFILE.md` | `660c4008a278252fe458c6d7106d8238057b7bf4` |
| `docs/architecture/v3/V3_1_NDEB_COMPATIBILITY_BINDING_1_0_0.md` | `f05e3d999af440ffe99bff0117cf57d13cd489af` |
| `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_AND_PERSISTENCE_ACTIVATION.md` | `ab48c47bd48b0a93aeb30a4386a12f5d799364ff` |
| `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_AND_PERSISTENCE_ACCEPTANCE_CRITERIA.md` | `35ad5e6fa4fa0d368d2a17098732d84cd207cab6` |
| `docs/architecture/v3/V3_2_CLIENT_DELIVERY_DOMAIN_MODEL.md` | `d2e0c76030d867a47d09414de5df5cc0056412c8` |
| `docs/architecture/v3/V3_2_CLIENT_DELIVERY_PERSISTENCE_ARCHITECTURE.md` | `e7cd75d8687d6086e16618ed264d746f2516c6b0` |
| `apps/api/pyproject.toml` | `87da4d8d3a71563b6626be5ba1a57f91475eeeac` |

## Canonical NEXUS authority lock

```text
NEXUS_CANONICAL_MAIN=
42f55f7db5769181f55470559cb31780d3196767

NEXUS_CANONICAL_TREE=
3692ac0f08b0726e236592cf7150643b254df884
```

The candidate binds the following exact upstream source objects:

| Upstream source | Git blob |
| --- | --- |
| `schemas/ndeb/v1/ndeb.schema.json` | `d7d1fe0bfac6b6e011cc15ae4e0ef3dc8ec08f1b` |
| `docs/architecture/ndeb/NDEB_SCHEMA_V1_SEMANTICS.md` | `dfe13e921cc73761c346c2285c9b2e2e9beb969e` |
| `src/ndeb/compatibility_fixtures.py` | `2a5b32bd7260ebd498c4085a7395a5456f2245e2` |
| `tests/test_ndeb_compatibility_fixtures.py` | `1a2b0da1712c913df588ce720261eab7d267ce11` |
| `src/ndeb/consumer_validation.py` | `9ccc0dd4f5d736473055d3aa02e1d460c846b5e3` |
| `tests/test_ndeb_consumer_validation.py` | `b0222fbb27ac7a38072a8c197c2fdea3f61d3f7d` |

Humanize does not copy these sources into local authority merely by referencing
them.

NEXUS remains authoritative for the NDEB exchange contract, semantics,
compatibility fixtures, and upstream consumer-validation evidence.

## Exact upstream contract identity

```text
SCHEMA_LANGUAGE=JSON Schema Draft 2020-12
SCHEMA_DOCUMENT_ID=urn:nexus:ndeb:schema:1.0.0
INSTANCE_SCHEMA_ID=urn:nexus:ndeb
INSTANCE_SCHEMA_VERSION=1.0.0
CANONICALIZATION=RFC8785+NFC
IDENTITY_MATERIAL_VERSION=1
NORMATIVE_NULL_POLICY=PROHIBITED
```

V3.3 must not infer a semver range.

V3.3 supports only the explicitly bound upstream schema identity and version.

## Canonical phase purpose

The canonical V3 phase plan assigns V3.3 this purpose:

```text
Implement the read-only Humanize NDEB consumption boundary.
```

V3.3 therefore owns the consumer-side architecture for:

- schema validation;
- integrity validation;
- tenant validation;
- engagement validation;
- classification validation;
- provenance validation;
- deterministic rejection of unsupported bundles.

## Activation prerequisites

The following prerequisites are satisfied for architecture preparation:

```text
V3_1_CANONICAL_CONSUMER_COMPATIBILITY_CONTRACT=SATISFIED
CANONICAL_UPSTREAM_NEXUS_EXCHANGE_SCHEMA=SATISFIED
CANONICAL_COMPATIBILITY_FIXTURE_SOURCE=SATISFIED
CANONICAL_CONSUMER_VALIDATION_SOURCE=SATISFIED
V3_1_BINDING_EFFECTIVE=YES
LOCAL_HUMANIZE_MAIN_CANONICALLY_ALIGNED=YES
```

Security review and dependency posture remain explicit V3.3 architecture and
implementation gates.

## Primary authority boundary

```text
NEXUS authoritative state
        |
        | separately authorized deterministic export
        v
NDEB artifact
        |
        | untrusted until validated
        v
Humanize V3.3 read-only consumption boundary
        |
        | VALIDATED only
        v
Humanize downstream delivery state
```

The V3.3 boundary may decide whether a candidate bundle is acceptable for
Humanize downstream use.

It may not decide what is true upstream.

## Read-only doctrine

```text
NDEB_CONSUMPTION_MODE=READ_ONLY
NEXUS_STATE_MUTATION_AUTHORITY=NONE
NEXUS_REPOSITORY_SCRAPING_AUTHORITY=NONE
DIRECT_NEXUS_DATABASE_ACCESS_AUTHORITY=NONE
NEXUS_INTERNAL_CLASS_DEPENDENCY_AUTHORITY=NONE
AUTHORITATIVE_NDEB_GENERATION_AUTHORITY=NONE
```

A consumer must not need repository scraping, direct database access, provider
calls, Humanize state, or model reconstruction to understand exported NDEB
evidence.

## Input acquisition boundary

This candidate does not select the production transport by which an authorized
NDEB artifact reaches Humanize.

```text
LIVE_NEXUS_ADAPTER_AUTHORITY=NONE
NDEB_TRANSPORT_SELECTION=UNRESOLVED
NETWORK_ACQUISITION_IMPLEMENTATION_AUTHORITY=NONE
```

V3.3 architecture begins at an already-acquired candidate artifact plus the
authorized Humanize tenant and engagement context required to evaluate it.

A later implementation gate must separately bind any file, API, object-store,
message, service-binding, or other transport mechanism before runtime use.

## Validation authority

The architecture package may define the deterministic validation pipeline and
its contracts.

It may define conceptual outcomes:

```text
VALIDATED
REJECTED
ERROR
```

It may not create executable enums, API schemas, database records, runtime
services, or persistence mappings in this gate.

## Stage 8 and Stage 9 relationship

NEXUS Stage 8 provides deterministic compatibility fixtures.

NEXUS Stage 9 provides deterministic consumer-observation validation with an
exact result domain of `VALIDATED`, `REJECTED`, and `ERROR`.

Humanize V3.3 must preserve the semantics of the bound upstream contract.

Humanize must not fork Stage 8 or Stage 9 into a competing source of truth.

```text
NEXUS_FIXTURE_COPY_AUTHORITY=NONE
NEXUS_CONSUMER_VALIDATOR_COPY_AUTHORITY=NONE
```

## V3.2 interlock

V3.2 defines the conceptual `Imported Bundle Reference` and downstream delivery
persistence boundary.

V3.3 may define the conditions under which an imported bundle is acceptable.

V3.3 does not gain persistence implementation authority from that relationship.

```text
PERSISTENCE_IMPLEMENTATION_AUTHORITY=NONE
DATABASE_SCHEMA_AUTHORITY=NONE
MIGRATION_AUTHORITY=NONE
```

## V3.4 interlock

V3.3 validates and preserves classification and provenance required at the
consumption boundary.

V3.4 remains responsible for provenance graph behavior, Claim Protection,
classification propagation, protected delivery facts, and
authority-preserving transformations.

```text
V3_3_CLASSIFICATION_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
V3_3_PROVENANCE_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
CLASSIFICATION_DOWNGRADE_AUTHORITY=NONE
PROVENANCE_REWRITE_AUTHORITY=NONE
CLAIM_LOCK_RUNTIME_AUTHORITY=NONE
PROTECTED_DELIVERY_FACT_RUNTIME_AUTHORITY=NONE
```

## Dependency posture

The canonical Humanize API dependency manifest does not currently declare a
JSON Schema validation library.

The presence of Pydantic does not, by itself, establish semantic equivalence to
the canonical upstream JSON Schema Draft 2020-12 contract.

Therefore:

```text
JSON_SCHEMA_VALIDATOR_SELECTION=UNRESOLVED
JSON_SCHEMA_VALIDATOR_SECURITY_REVIEW=PENDING_LATER_GATE
NEW_DEPENDENCY_INSTALLATION_AUTHORITY=NONE
PYPROJECT_MUTATION_AUTHORITY=NONE
PACKAGE_LOCK_MUTATION_AUTHORITY=NONE
```

## Security posture

A candidate NDEB artifact is untrusted until all required validation succeeds.

The architecture must account for:

- malformed serialization;
- schema confusion;
- unsupported identity or version;
- invalid or unverifiable integrity;
- tenant mismatch;
- engagement mismatch;
- missing or invalid provenance;
- missing, ambiguous, unsupported-required, or downgraded classification;
- unsupported required extensions;
- ambiguous or dangling references;
- excessive bundle size;
- excessive collection cardinality;
- excessive nesting depth;
- parser resource exhaustion;
- hash/canonicalization resource exhaustion;
- duplicate or ambiguous identity material;
- implementation dependency risk.

Concrete numeric resource limits are not established by the canonical sources
reviewed for this package.

They remain unresolved until a separately reviewed implementation/security
gate.

## Package contents

This V3.3 candidate package consists of exactly four documents:

```text
docs/architecture/v3/V3_3_NDEB_BUNDLE_INGESTION_AND_VALIDATION_ACTIVATION.md
docs/architecture/v3/V3_3_NDEB_INGESTION_AND_VALIDATION_ARCHITECTURE.md
docs/architecture/v3/V3_3_NDEB_VALIDATION_AND_REJECTION_MATRIX.md
docs/architecture/v3/V3_3_NDEB_BUNDLE_INGESTION_AND_VALIDATION_ACCEPTANCE_CRITERIA.md
```

## Explicit non-authority

```text
V3_3_IMPLEMENTATION_AUTHORITY=NONE
LIVE_NDEB_ADAPTER_IMPLEMENTATION_AUTHORITY=NONE
NDEB_INGESTION_RUNTIME_AUTHORITY=NONE
NDEB_SCHEMA_VALIDATOR_RUNTIME_AUTHORITY=NONE
API_ROUTE_AUTHORITY=NONE
DOMAIN_MODEL_IMPLEMENTATION_AUTHORITY=NONE
PERSISTENCE_IMPLEMENTATION_AUTHORITY=NONE
DATABASE_SCHEMA_AUTHORITY=NONE
DEPENDENCY_INSTALLATION_AUTHORITY=NONE
PYPROJECT_MUTATION_AUTHORITY=NONE
FIXTURE_COPY_OR_FORK_AUTHORITY=NONE
NEXUS_SOURCE_MUTATION_AUTHORITY=NONE
DEPLOYMENT_AUTHORITY=NONE
EXPORT_AUTHORITY=NONE
CLIENT_RELEASE_AUTHORITY=NONE
```

## Candidate effective point

Preparing or independently accepting these four detached candidate documents
does not activate V3.3 architecture canonically.

The architecture package becomes canonical only after a separately authorized
repository lifecycle merges the exact accepted package to Humanize `main` and
an independent post-merge canonical reconciliation passes.

Even that architecture effective point does not automatically grant V3.3
runtime implementation authority.

## Final invariant

Humanize may validate whether an explicitly supported NDEB artifact is safe and
compatible for downstream consumption.

Humanize must not use validation as a mechanism to acquire upstream evidence
authority.
