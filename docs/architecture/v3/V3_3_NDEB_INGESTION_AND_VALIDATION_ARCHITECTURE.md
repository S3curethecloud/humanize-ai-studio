# Humanize V3.3 NDEB Ingestion and Validation Architecture

## Status

```text
V3_3_ARCHITECTURE_STATUS=NONCANONICAL_CANDIDATE
V3_3_IMPLEMENTATION_AUTHORITY=NONE
```

This document defines the candidate architecture for the Humanize V3.3
read-only NDEB consumption boundary.

It does not implement the boundary.

## Architecture objective

Provide a deterministic, fail-closed Humanize consumer boundary that accepts
only an explicitly supported NDEB contract and prevents unvalidated,
cross-tenant, cross-engagement, integrity-invalid, classification-invalid, or
provenance-invalid bundles from entering downstream delivery workflows.

## Authoritative contract

The exact supported upstream contract is:

```text
SCHEMA_LANGUAGE=JSON Schema Draft 2020-12
SCHEMA_DOCUMENT_ID=urn:nexus:ndeb:schema:1.0.0
INSTANCE_SCHEMA_ID=urn:nexus:ndeb
INSTANCE_SCHEMA_VERSION=1.0.0
CANONICALIZATION=RFC8785+NFC
IDENTITY_MATERIAL_VERSION=1
NORMATIVE_NULL_POLICY=PROHIBITED
```

Exact-version support applies.

No semver range is inferred.

## Source authority model

NEXUS owns:

- authoritative NDEB schema definition;
- NDEB semantic rules;
- authoritative NDEB generation;
- source evidence;
- tenant and engagement truth;
- upstream classification authority;
- upstream provenance authority;
- deterministic export authorization;
- canonical compatibility fixtures;
- canonical consumer-validation evidence.

Humanize V3.3 owns only the downstream decision to accept or refuse a candidate
bundle for Humanize consumption under the explicitly bound compatibility
profile.

## Trust model

Before validation:

```text
CANDIDATE_BUNDLE_TRUST=UNTRUSTED
CANDIDATE_BUNDLE_AUTHORITY=UNESTABLISHED_FOR_HUMANIZE_CONSUMPTION
```

After successful validation:

```text
CANDIDATE_BUNDLE_CONSUMPTION_DISPOSITION=VALIDATED
UPSTREAM_AUTHORITY_OWNERSHIP=NEXUS
HUMANIZE_AUTHORITY=DOWNSTREAM_CONSUMPTION_ONLY
```

Validation does not change upstream approval, evidence, classification,
provenance, or export authority.

## Consumption boundary

The runtime architecture, when separately authorized, must conceptually accept:

1. candidate NDEB bytes or an equivalent bounded parsed representation derived
   from those bytes;
2. the exact supported Humanize compatibility binding;
3. authorized Humanize tenant context;
4. authorized Humanize engagement context;
5. the exact canonical upstream schema/semantic contract required by the
   binding.

The acquisition transport is not selected by this package.

## Transport non-selection

```text
NDEB_TRANSPORT_SELECTION=UNRESOLVED
LIVE_NEXUS_ADAPTER_AUTHORITY=NONE
NETWORK_ACQUISITION_IMPLEMENTATION_AUTHORITY=NONE
```

The architecture must not assume that transport success establishes bundle
validity.

Transport authenticity, if introduced later, is an input to validation and not
a substitute for schema, integrity, scope, classification, or provenance
checks.

## Conceptual pipeline

The candidate architecture requires this fail-closed logical sequence:

```text
candidate artifact
    |
    v
bounded decode / parse
    |
    v
schema identity + version gate
    |
    v
JSON Schema structural validation
    |
    v
normative NDEB semantic validation
    |
    v
integrity validation
    |
    v
tenant + engagement binding validation
    |
    v
classification + provenance validation
    |
    v
compatibility / required-extension validation
    |
    v
deterministic disposition
    |
    +--> VALIDATED --> eligible for later downstream Humanize use
    |
    +--> REJECTED  --> fail closed
    |
    +--> ERROR     --> fail closed
```

This is a logical architecture.

The exact function decomposition, class names, modules, API shapes, and data
types remain implementation-gate work.

## Bounded decode and parse

A future implementation must treat candidate bytes as untrusted input.

Malformed serialization must fail closed.

The implementation must not silently repair malformed input.

The implementation must not infer missing fields from filenames, directories,
transport metadata, narrative content, or prior Humanize state.

Concrete JSON parser selection is not authorized here.

Concrete input byte limits, nesting limits, and collection cardinality limits
remain unresolved pending a dedicated implementation/security review.

## Schema identity and version gate

The exact Humanize supported pair is:

```text
schema_id=urn:nexus:ndeb
schema_version=1.0.0
```

The validator must not:

- infer schema identity from document shape;
- alias an unofficial identity into canonical status;
- accept a future or historical version because it appears semver-compatible;
- silently coerce version strings;
- negotiate a version not explicitly bound by Humanize governance.

An available but unsupported identity or version produces fail-closed
incompatibility.

## Structural schema validation

The upstream schema language is JSON Schema Draft 2020-12.

Structural validation must be performed against the exact canonical schema
object bound by the accepted Humanize compatibility record.

The architecture must not reconstruct an approximate local schema from
Pydantic models or hand-maintained field lists.

A local cache or vendored schema artifact, if later proposed, requires explicit
identity and update governance.

No such implementation is authorized by this package.

## Schema validator dependency posture

Canonical Humanize currently has no declared JSON Schema validator library.

Therefore implementation must not assume one exists.

Before runtime authorization, a separate gate must establish:

- chosen validator;
- Draft 2020-12 support;
- exact behavior required by the NDEB schema;
- dependency provenance;
- licensing posture if applicable;
- security posture;
- deterministic behavior;
- offline/reproducible execution posture;
- version pinning or bounded version policy;
- test evidence against canonical fixtures;
- failure behavior.

```text
JSON_SCHEMA_VALIDATOR_SELECTION=UNRESOLVED
DEPENDENCY_INSTALLATION_AUTHORITY=NONE
```

## Normative semantic validation

JSON Schema validation is necessary but not sufficient.

The canonical NDEB semantics explicitly reserve normative checks that are not
fully expressed by local lexical and structural JSON Schema constraints.

V3.3 must therefore preserve a second semantic-validation layer for applicable
rules including:

- deterministic ordering;
- key-based uniqueness;
- temporal comparison where required by upstream semantics;
- referential closure;
- manifest/item equality;
- classification fail-closed behavior;
- NFC comparison;
- required-extension support;
- digest equality.

Humanize may implement these checks only after a separately reviewed runtime
gate establishes their exact mapping to the canonical NEXUS semantics.

Humanize must not weaken or reinterpret them.

## Closed-world object posture

Canonical NDEB v1 requires all top-level fields.

Unknown top-level fields are prohibited.

Normative objects are closed except the explicit extension payload surface.

Optional fields are omitted when absent.

Normative null values are prohibited.

V3.3 must preserve this posture.

## Required and optional extensions

`required_extensions` is governed by the canonical NDEB semantics.

Every required extension name must resolve to an exact key in `extensions`.

Unknown optional extension objects may be preserved without interpretation
when canonical semantics permit them.

Unsupported required extensions fail closed.

V3.3 must not execute extension payloads merely because they are present.

No plugin or dynamic-code loading authority is created by an NDEB extension.

## Integrity model

The canonical integrity contract includes:

```text
algorithm=sha-256
canonicalization=RFC8785+NFC
identity_material_version=1
content_digest_sha256=<64 lowercase hexadecimal characters>
bundle_id=ndeb:sha256:<digest>
```

The canonical semantics define the identity material boundary.

`bundle_id` and `integrity.content_digest_sha256` are excluded from the
pre-digest identity material.

All other normative material participates.

A future V3.3 implementation must independently verify the canonical integrity
contract rather than trusting the provided digest value.

## Canonicalization dependency posture

RFC8785 plus NFC canonicalization is a security- and identity-sensitive
operation.

The package does not select a canonicalization library or implementation.

Before runtime authority, an implementation gate must establish exact
canonicalization behavior and test it against canonical upstream evidence.

```text
CANONICALIZATION_IMPLEMENTATION_SELECTION=UNRESOLVED
INTEGRITY_RUNTIME_AUTHORITY=NONE
```

## Tenant binding

`tenant_id` is an authoritative public exchange identity.

It must not be inferred, reconstructed, substituted, defaulted, or repaired by
Humanize.

A future validation decision must compare the authoritative bundle tenant
identity to the separately authorized Humanize tenant context.

If both are established and they differ, consumption is rejected.

If the required Humanize tenant authority or required bundle identity cannot be
established, validation errors fail closed.

Cross-tenant reuse is prohibited absent a future separately reviewed contract.

## Engagement binding

`engagement_id` is an authoritative public exchange identity.

It must not be inferred from:

- presentation content;
- engagement names;
- filenames;
- directory paths;
- user-entered narrative;
- prior local storage;
- model output.

A future validation decision must compare the authoritative bundle engagement
identity with the separately authorized Humanize engagement context.

A mismatch fails closed.

## Classification validation

The canonical NDEB classification object carries a value and authority
reference.

Missing, ambiguous, unsupported-required, or downgraded classification fails
closed under the canonical semantics.

V3.3 may:

- validate required classification presence and structure;
- validate the bundle's classification against canonical semantics;
- validate compatibility with the authorized Humanize context when that policy
  is separately defined;
- preserve the classification for later phases.

V3.3 may not:

- downgrade classification;
- invent classification;
- rewrite upstream classification authority;
- treat a Humanize presentation label as upstream evidence authority.

Exact propagation and Claim Protection behavior remain V3.4 responsibilities.

## Provenance validation

Canonical NDEB provenance includes explicit provenance entries and references.

The normative semantics require referential closure for applicable provenance
references.

V3.3 must fail closed when required provenance authority cannot be established.

V3.3 may validate and preserve provenance.

V3.3 may not rewrite or synthesize provenance to make an invalid bundle pass.

Deep provenance graph behavior and downstream Claim Protection remain V3.4
responsibilities.

## Artifact and manifest reference closure

The canonical semantics require exact internal joins among manifest entries,
evidence items, artifact references, provenance references, and applicable
approval references.

Duplicate, missing, dangling, or ambiguous join identities fail closed.

V3.3 semantic validation must eventually cover the exact canonical closure
rules relevant to the supported NDEB version.

It must not substitute human-readable names for authoritative identifiers.

## Compatibility fixture posture

Canonical Stage 8 fixtures cover deterministic cases including:

- supported canonical schema;
- supported governed version;
- unsupported future version;
- unsupported historical version;
- unknown required field;
- unknown optional extension field;
- incompatible semantic change;
- upstream identity mismatch;
- tenant scope mismatch;
- engagement scope mismatch;
- destination binding invalidity;
- policy provenance invalidity;
- unauthorized upstream export posture;
- upstream issues present;
- security-boundary violation;
- malformed fixture envelope.

V3.3 implementation acceptance must later demonstrate compatibility behavior
against the exact canonical cases or an explicitly reviewed equivalent
mechanism.

This package does not authorize copying Stage 8 source into Humanize.

## Consumer-validation posture

Canonical Stage 9 establishes an exact disposition domain:

```text
VALIDATED
REJECTED
ERROR
```

It also establishes deterministic issue categories for schema identity,
schema version, tenant, engagement, classification, provenance, integrity, and
consumer-observation evidence.

V3.3 preserves this outcome model at the architecture level.

Humanize-specific executable error classes and API status mappings remain
implementation work.

## Disposition precedence

The candidate architecture requires safe precedence:

1. inability to safely parse or establish required validation authority leads
   to `ERROR`;
2. deterministic incompatibility or mismatch with established authoritative
   values leads to `REJECTED`;
3. `VALIDATED` is available only after every required dimension passes.

No partial success is equivalent to `VALIDATED`.

A bundle with both errors and rejection evidence must not be accepted.

Exact executable issue ordering and serialization must be frozen before
implementation.

## Determinism

For identical logical inputs and identical bound authority references, V3.3
validation must produce identical logical output.

The deterministic core must not require:

- network calls;
- provider calls;
- model calls;
- tool calls;
- persistence mutation;
- wall-clock-dependent decisions;
- nondeterministic random values.

Transport acquisition may later occur outside that deterministic core under
separate authority.

## Side-effect posture

Validation itself must be side-effect free with respect to NEXUS.

A failed validation must not mutate NEXUS.

A successful validation must not mutate NEXUS.

The core validation decision should be computable before any downstream
Humanize persistence mutation.

```text
NEXUS_MUTATION_AUTHORITY=NONE
PERSISTENCE_MUTATION_AUTHORITY=NONE
```

## V3.2 downstream handoff

A `VALIDATED` result may later make the bundle eligible to create or update a
Humanize `Imported Bundle Reference` under separately authorized persistence
rules.

This package does not authorize that persistence.

A `REJECTED` or `ERROR` result must never be treated as accepted evidence merely
because raw bytes are retained for diagnostics under some future authorized
operational design.

## V3.4 handoff

V3.3 hands later phases a validation decision plus preserved source authority
needed for downstream use.

V3.3 does not authorize:

- protected delivery facts;
- claim locking;
- classification transformation;
- provenance graph mutation;
- governed composition.

## Observability boundary

Future runtime implementation should make validation decisions auditable
without exposing restricted bundle material unnecessarily.

This package does not define log schemas, telemetry sinks, retention, or
redaction policy.

Those operational details require separate review.

Validation diagnostics must not silently leak tenant, engagement,
classification, or sensitive evidence content.

## Resource-abuse boundary

Before implementation authority, security review must freeze bounded behavior
for at least:

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

The canonical sources reviewed for this candidate do not provide Humanize
numeric values for these controls.

This candidate therefore does not invent them.

## Error information boundary

Diagnostic detail must distinguish operator/debug evidence from externally
safe error information.

A later API gate must prevent detailed parser, schema, provenance, or
classification diagnostics from becoming an information-disclosure surface.

No API status code or response body is defined here.

## Concurrency and replay

The deterministic validation core should be safe to recompute for identical
logical inputs.

This candidate does not define caching, deduplication, idempotency storage,
replay windows, or request concurrency controls.

Those are later implementation/operations concerns.

## Version change control

NEXUS `main` advancing does not automatically change Humanize compatibility.

Humanize compatibility changes only through an explicitly reviewed binding for
a supported upstream identity/version.

A future NDEB version must not be silently accepted by this V3.3 architecture.

## Explicit implementation non-authority

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
DEPENDENCY_INSTALLATION_AUTHORITY=NONE
PYPROJECT_MUTATION_AUTHORITY=NONE
DEPLOYMENT_AUTHORITY=NONE
```

## Final architecture invariant

A Humanize bundle is eligible for downstream use only after the supported
consumer contract is deterministically established.

Humanize validation may gate consumption.

It may not rewrite the evidence it validates or become the authority that
created that evidence.
