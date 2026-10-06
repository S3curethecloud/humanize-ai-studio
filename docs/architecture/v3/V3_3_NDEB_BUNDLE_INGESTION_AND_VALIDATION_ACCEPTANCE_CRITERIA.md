# Humanize V3.3 NDEB Bundle Ingestion and Validation Acceptance Criteria

## Status

```text
V3_3_ACCEPTANCE_CRITERIA_STATUS=NONCANONICAL_CANDIDATE
V3_3_IMPLEMENTATION_AUTHORITY=NONE
```

These criteria govern acceptance of the V3.3 architecture package.

They do not constitute runtime acceptance.

## A. Package identity

Acceptance requires exactly these four package documents:

```text
docs/architecture/v3/V3_3_NDEB_BUNDLE_INGESTION_AND_VALIDATION_ACTIVATION.md
docs/architecture/v3/V3_3_NDEB_INGESTION_AND_VALIDATION_ARCHITECTURE.md
docs/architecture/v3/V3_3_NDEB_VALIDATION_AND_REJECTION_MATRIX.md
docs/architecture/v3/V3_3_NDEB_BUNDLE_INGESTION_AND_VALIDATION_ACCEPTANCE_CRITERIA.md
```

No executable source file is part of this architecture package.

No dependency manifest change is part of this architecture package.

## B. Canonical Humanize base

Acceptance requires the package to remain bound to:

```text
HUMANIZE_CANONICAL_MAIN=
ae40c2a84ba7d41c36b56f3512c4a80b7ff2dd6e

HUMANIZE_CANONICAL_TREE=
330e6e5d56f687b2bef4c60dc8aafd0839891ab9
```

The package must preserve:

```text
V3_1_BINDING_EFFECTIVE=YES
V3_1_SUPPORTED_UPSTREAM_SCHEMA_IDENTITY=urn:nexus:ndeb
V3_1_SUPPORTED_UPSTREAM_SCHEMA_VERSION=1.0.0
```

It must not rewrite historical V3.1 unbound source records.

## C. Canonical NEXUS source lock

Acceptance requires exact binding to:

```text
NEXUS_CANONICAL_MAIN=
42f55f7db5769181f55470559cb31780d3196767

NEXUS_CANONICAL_TREE=
3692ac0f08b0726e236592cf7150643b254df884
```

Required upstream source identities:

```text
NDEB_SCHEMA_BLOB=d7d1fe0bfac6b6e011cc15ae4e0ef3dc8ec08f1b
NDEB_SEMANTICS_BLOB=dfe13e921cc73761c346c2285c9b2e2e9beb969e
STAGE8_COMPATIBILITY_FIXTURES_BLOB=2a5b32bd7260ebd498c4085a7395a5456f2245e2
STAGE8_COMPATIBILITY_FIXTURE_TEST_BLOB=1a2b0da1712c913df588ce720261eab7d267ce11
STAGE9_CONSUMER_VALIDATION_BLOB=9ccc0dd4f5d736473055d3aa02e1d460c846b5e3
STAGE9_CONSUMER_VALIDATION_TEST_BLOB=b0222fbb27ac7a38072a8c197c2fdea3f61d3f7d
```

Any source-lock mismatch requires a new review.

## D. Supported schema contract

Acceptance requires exact preservation of:

```text
SCHEMA_LANGUAGE=JSON Schema Draft 2020-12
SCHEMA_DOCUMENT_ID=urn:nexus:ndeb:schema:1.0.0
INSTANCE_SCHEMA_ID=urn:nexus:ndeb
INSTANCE_SCHEMA_VERSION=1.0.0
CANONICALIZATION=RFC8785+NFC
IDENTITY_MATERIAL_VERSION=1
NORMATIVE_NULL_POLICY=PROHIBITED
```

No semver compatibility range may be inferred.

## E. Read-only authority boundary

Acceptance requires:

```text
NDEB_CONSUMPTION_MODE=READ_ONLY
NEXUS_STATE_MUTATION_AUTHORITY=NONE
NEXUS_REPOSITORY_SCRAPING_AUTHORITY=NONE
DIRECT_NEXUS_DATABASE_ACCESS_AUTHORITY=NONE
NEXUS_INTERNAL_CLASS_DEPENDENCY_AUTHORITY=NONE
AUTHORITATIVE_NDEB_GENERATION_AUTHORITY=NONE
```

The package must not make NEXUS depend on Humanize.

## F. Input acquisition boundary

Acceptance requires the package to state explicitly that production transport
is unresolved.

It must not silently select filesystem ingestion, direct NEXUS API, object
store, message bus, service binding, database access, or repository access.

A later transport implementation requires its own authority.

## G. Schema validation architecture

Acceptance requires both:

1. exact JSON Schema structural validation against the canonical supported
   schema;
2. normative semantic validation for canonical NDEB rules not fully expressed
   by JSON Schema.

The package must not claim that hand-written Pydantic models are equivalent to
the canonical upstream JSON Schema without separately reviewed evidence.

## H. Dependency posture

Acceptance requires:

```text
JSON_SCHEMA_VALIDATOR_SELECTION=UNRESOLVED
NEW_DEPENDENCY_INSTALLATION_AUTHORITY=NONE
PYPROJECT_MUTATION_AUTHORITY=NONE
PACKAGE_LOCK_MUTATION_AUTHORITY=NONE
```

A future dependency-selection gate must review exact Draft 2020-12 support,
security, deterministic behavior, version policy, and canonical-fixture
evidence.

## I. Integrity validation

Acceptance requires the architecture to preserve the canonical integrity
contract:

```text
algorithm=sha-256
canonicalization=RFC8785+NFC
identity_material_version=1
```

The package must distinguish trusting a supplied digest from independently
verifying the canonical identity material.

The package must not select a canonicalization implementation without review.

## J. Tenant validation

Acceptance requires:

- bundle tenant identity is authoritative upstream data;
- Humanize tenant context is separately authorized local context;
- neither may be inferred from narrative or path information;
- mismatch fails closed;
- missing required authority fails closed;
- cross-tenant implicit reuse is prohibited.

## K. Engagement validation

Acceptance requires:

- bundle engagement identity is authoritative upstream data;
- Humanize engagement context is separately authorized local context;
- neither may be inferred from narrative similarity;
- mismatch fails closed;
- missing required authority fails closed;
- cross-engagement implicit reuse is prohibited.

## L. Classification validation

Acceptance requires V3.3 to validate and preserve classification only.

The package must not authorize classification downgrade, classification
invention, replacement of upstream authority, Claim Lock runtime, or downstream
classification transformation.

Those later behaviors remain outside V3.3.

## M. Provenance validation

Acceptance requires V3.3 to validate and preserve required provenance.

The package must require fail-closed behavior for missing, malformed, dangling,
ambiguous, or otherwise unestablishable required provenance.

The package must not authorize provenance synthesis or rewrite.

## N. Referential and semantic closure

Acceptance requires recognition that JSON Schema validation alone is
insufficient for all canonical NDEB semantics.

Later implementation must cover applicable rules for:

- deterministic ordering;
- semantic uniqueness;
- referential closure;
- manifest/evidence equality;
- required-extension support;
- digest equality;
- classification fail-closed behavior;
- NFC comparison;
- canonical temporal rules where applicable.

## O. Extension behavior

Acceptance requires:

- unknown optional extension objects may be preserved only as allowed by
  canonical NDEB rules;
- required extension names must resolve exactly;
- unsupported required extension semantics fail closed;
- extension payloads do not authorize executable code or plugins.

## P. Compatibility fixtures

Acceptance requires the package to preserve Stage 8 as upstream authority.

The architecture must account for at least:

- supported canonical schema;
- supported governed version;
- unsupported future version;
- unsupported historical version;
- unknown required field;
- unknown optional extension field;
- incompatible semantic change;
- tenant mismatch;
- engagement mismatch;
- policy provenance invalidity;
- security-boundary violation.

The package must not copy or fork Stage 8 source as a new Humanize authority.

## Q. Consumer validation

Acceptance requires the exact logical result domain:

```text
VALIDATED
REJECTED
ERROR
```

The package must preserve Stage 9's deterministic, fail-closed consumer posture.

It must not infer compatibility from narrative plausibility.

## R. Deterministic matrix

Acceptance requires an explicit matrix that covers:

- exact supported identity/version;
- unsupported identity/version;
- malformed input;
- structural validation failure;
- integrity absence/mismatch;
- tenant absence/mismatch;
- engagement absence/mismatch;
- classification absence/mismatch/downgrade;
- provenance absence/incompatibility;
- extension behavior;
- internal referential closure;
- validator/dependency unavailability;
- security-boundary violation;
- resource-limit failure.

Every case must fail closed unless every required validation succeeds.

## S. Disposition precedence

Acceptance requires:

```text
ANY_ERROR_CONDITION => ERROR
NO_ERROR_AND_ANY_REJECTION_CONDITION => REJECTED
NO_ERROR_AND_NO_REJECTION_AND_ALL_REQUIRED_VALIDATIONS_PASS
  => VALIDATED
```

No partial-success state may enter downstream Humanize workflows.

## T. Deterministic core

Acceptance requires the future validation core to avoid required dependence on:

- network access;
- provider access;
- model calls;
- tool calls;
- persistence mutation;
- random values;
- wall-clock-dependent compatibility decisions.

Transport acquisition may be separate.

The logical validation decision must remain deterministic.

## U. Security and resource limits

Acceptance requires the architecture to identify, without inventing numeric
values, the need to freeze at implementation time:

```text
MAX_BUNDLE_BYTES
MAX_NESTING_DEPTH
MAX_COLLECTION_CARDINALITY
MAX_STRING_OR_FIELD_SIZE_WHERE_REQUIRED
CANONICALIZATION_WORK_LIMIT
HASH_VALIDATION_WORK_LIMIT
MALFORMED_JSON_POLICY
DUPLICATE_JSON_MEMBER_POLICY
```

Runtime implementation must not be authorized while required safety limits
remain materially unresolved.

## V. V3.2 boundary

Acceptance requires V3.3 to remain separate from persistence implementation.

A `VALIDATED` result may become eligible for later persistence through the
V3.2 domain boundary.

This package does not authorize creation or mutation of an `Imported Bundle
Reference`.

## W. V3.4 boundary

Acceptance requires:

```text
V3_3_CLASSIFICATION_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
V3_3_PROVENANCE_AUTHORITY=VALIDATE_AND_PRESERVE_ONLY
CLAIM_LOCK_RUNTIME_AUTHORITY=NONE
PROTECTED_DELIVERY_FACT_RUNTIME_AUTHORITY=NONE
```

V3.3 must not preempt V3.4.

## X. Diagnostic boundary

Acceptance requires diagnostics to remain non-authoritative.

The package must not define public API error detail that could leak sensitive
tenant, engagement, classification, provenance, or evidence content.

Exact API mapping remains later work.

## Y. Explicit non-authority

Architecture-package acceptance must preserve:

```text
V3_3_IMPLEMENTATION_AUTHORITY=NONE
LIVE_NDEB_ADAPTER_IMPLEMENTATION_AUTHORITY=NONE
NDEB_INGESTION_RUNTIME_AUTHORITY=NONE
NDEB_SCHEMA_VALIDATOR_RUNTIME_AUTHORITY=NONE
INTEGRITY_RUNTIME_AUTHORITY=NONE
API_ROUTE_AUTHORITY=NONE
DOMAIN_MODEL_IMPLEMENTATION_AUTHORITY=NONE
PERSISTENCE_IMPLEMENTATION_AUTHORITY=NONE
DATABASE_SCHEMA_AUTHORITY=NONE
MIGRATION_AUTHORITY=NONE
DEPENDENCY_INSTALLATION_AUTHORITY=NONE
PYPROJECT_MUTATION_AUTHORITY=NONE
FIXTURE_COPY_OR_FORK_AUTHORITY=NONE
NEXUS_SOURCE_MUTATION_AUTHORITY=NONE
DEPLOYMENT_AUTHORITY=NONE
EXPORT_AUTHORITY=NONE
CLIENT_RELEASE_AUTHORITY=NONE
```

## Z. Architecture-package closure

This candidate package is not canonical merely because it is prepared or
independently accepted.

Architecture closure requires a separately governed repository lifecycle:

1. exact candidate acceptance;
2. repository materialization authorization and execution;
3. staging authorization and execution;
4. commit authorization and execution;
5. remote publication authorization and execution;
6. pull-request creation and acceptance;
7. ready transition where separately governed;
8. merge authorization and execution;
9. independent post-merge canonical identity, scope, and authority
   reconciliation;
10. local canonical-main realignment where necessary.

Only after that architecture closure may a separate V3.3 implementation
activation/readiness review consider executable work.

## Final acceptance invariant

The package passes only if it defines a deterministic, fail-closed, read-only
NDEB validation boundary without silently selecting runtime implementation
details or acquiring upstream NEXUS authority.
