# Humanize V3.3 NDEB Validation and Rejection Matrix

## Status

```text
V3_3_VALIDATION_MATRIX_STATUS=NONCANONICAL_CANDIDATE
V3_3_IMPLEMENTATION_AUTHORITY=NONE
```

This matrix defines candidate architecture-level validation outcomes for the
supported NDEB `urn:nexus:ndeb` version `1.0.0`.

It is not an executable enum, API contract, exception hierarchy, persistence
schema, or wire protocol.

## Outcome domain

V3.3 preserves the canonical Stage 9 logical disposition domain:

```text
VALIDATED
REJECTED
ERROR
```

### VALIDATED

Every required validation dimension passes for the exact supported Humanize
binding.

`VALIDATED` means eligible for later downstream Humanize consumption.

It does not mean Humanize created the evidence, changed upstream approval,
authorized export, authorized client release, or may mutate NEXUS.

### REJECTED

Required authority and observation evidence are available and establish an
incompatibility, mismatch, or unsupported condition.

The candidate bundle is not eligible for downstream Humanize consumption.

### ERROR

Required validation authority, required validation evidence, or safe
interpretation cannot be established.

The candidate bundle is not eligible for downstream Humanize consumption.

## Fail-closed rule

```text
REJECTED -> NO_CONSUMPTION
ERROR    -> NO_CONSUMPTION
```

There is no best-effort acceptance state.

There is no implicit compatibility state.

## Matrix

| Case | Required observation | Candidate disposition | Architecture rationale |
| --- | --- | --- | --- |
| Exact supported `schema_id=urn:nexus:ndeb` and `schema_version=1.0.0`; every required validation passes | Complete authoritative input | `VALIDATED` | Exact supported contract is established |
| Unsupported schema identity | Identity is present and unambiguous | `REJECTED` | Humanize supports only the explicitly bound identity |
| Unsupported future schema version | Version is present and unambiguous | `REJECTED` | No forward-compatible version range is inferred |
| Unsupported historical schema version | Version is present and unambiguous | `REJECTED` | No backward-compatible version range is inferred |
| Missing or unparseable schema identity/version | Required identity cannot be safely established | `ERROR` | Compatibility authority cannot be established |
| Malformed serialization | Candidate cannot be safely decoded | `ERROR` | Validation cannot proceed safely |
| Supported identity/version but JSON Schema structural validation fails | Exact failure evidence available | `ERROR` | Candidate does not satisfy the exact supported structural contract |
| Unknown prohibited top-level field | Exact schema failure evidence available | `ERROR` | NDEB v1 top-level posture is closed-world |
| Unknown optional extension permitted by canonical extension rules | Required extension rules otherwise satisfied | Continue validation; may reach `VALIDATED` | Canonical semantics permit preservation without interpretation |
| Unsupported required extension | Required extension is present but unsupported for safe interpretation | `ERROR` | Required semantics cannot be safely established |
| Incompatible semantic change under the same nominal version | Deterministic incompatibility established | `REJECTED` | Nominal identity/version does not override semantic incompatibility |
| Missing normative required field | Required contract evidence absent | `ERROR` | Required validation authority cannot be established |
| Normative null where prohibited | Exact invalid value observed | `ERROR` | Canonical null policy is `PROHIBITED` |
| Integrity metadata missing or malformed | Required integrity evidence unavailable | `ERROR` | Integrity authority cannot be established |
| Supported integrity metadata present but digest does not match recomputed canonical identity material | Expected and observed values are established | `REJECTED` | Deterministic integrity mismatch |
| `bundle_id` inconsistent with the verified digest | Expected and observed identities are established | `REJECTED` | Bundle identity does not bind to verified content |
| Unsupported integrity algorithm/canonicalization/material version | Values are explicit but unsupported | `REJECTED` | Exact supported integrity contract not satisfied |
| Humanize tenant context unavailable | Required local authority absent | `ERROR` | Tenant authorization cannot be established |
| Bundle `tenant_id` missing/malformed | Required upstream authority absent | `ERROR` | Tenant authority cannot be established |
| Bundle tenant differs from authorized Humanize tenant | Both authoritative values established | `REJECTED` | Cross-tenant consumption is forbidden |
| Humanize engagement context unavailable | Required local authority absent | `ERROR` | Engagement authorization cannot be established |
| Bundle `engagement_id` missing/malformed | Required upstream authority absent | `ERROR` | Engagement authority cannot be established |
| Bundle engagement differs from authorized Humanize engagement | Both authoritative values established | `REJECTED` | Cross-engagement implicit reuse is forbidden |
| Classification missing, malformed, ambiguous, or unsupported-required | Required classification authority cannot be established | `ERROR` | Canonical classification semantics fail closed |
| Classification is established but conflicts with separately authorized Humanize consumption context | Both sides established | `REJECTED` | Deterministic classification incompatibility |
| Attempted classification downgrade | Source and attempted handling are established | `REJECTED` | Humanize must not weaken upstream classification |
| Required provenance absent, malformed, dangling, or ambiguous | Provenance authority cannot be safely established | `ERROR` | Required source traceability is not established |
| Required provenance is complete but deterministically incompatible with the bound observation/contract | Expected and observed authority established | `REJECTED` | Complete evidence proves incompatibility |
| Duplicate, missing, dangling, or ambiguous internal join identity | Referential closure cannot be safely established | `ERROR` | Canonical semantics fail closed |
| Manifest/evidence equality rule fails | Both sides are established | `REJECTED` | Deterministic semantic mismatch |
| Required deterministic ordering/uniqueness rule fails | Complete candidate structure available | `REJECTED` | Candidate is incompatible with canonical normative semantics |
| Canonicalization cannot be performed safely | Required integrity procedure unavailable or fails | `ERROR` | Integrity cannot be established |
| Required validation dependency unavailable | Validator authority unavailable | `ERROR` | Runtime cannot claim validation without the required implementation |
| Canonical schema object identity cannot be established | Required schema authority unavailable | `ERROR` | Validator must not run against an approximate schema |
| Compatibility fixture reference required by a test/validation path cannot be resolved | Required reference evidence absent | `ERROR` | Compatibility evidence cannot be established |
| Complete observation disagrees with expected compatibility disposition | Expected and observed results established | `REJECTED` | Canonical Stage 9 treats disposition mismatch as rejection |
| Complete observation disagrees with expected issue set | Expected and observed results established | `REJECTED` | Canonical Stage 9 treats issue mismatch as rejection |
| Consumer identity required by a later implementation is missing | Required consumer authority absent | `ERROR` | Canonical Stage 9 treats missing consumer identity as error |
| Consumer contract reference required by a later implementation is invalid | Required contract authority absent | `ERROR` | Canonical Stage 9 treats invalid contract reference as error |
| Required validation observation evidence is incomplete | Required evidence absent | `ERROR` | Canonical Stage 9 treats incomplete observation evidence as error |
| Security-boundary violation prevents trustworthy consumption | Boundary authority cannot safely be established | `ERROR` | Canonical Stage 8 security-boundary violations fail closed |
| Candidate exceeds separately authorized resource limits | Bounded limit exceeded | `ERROR` | Safe validation cannot proceed |
| Internal validator contradiction or impossible state | Validator cannot establish a trustworthy decision | `ERROR` | Fail closed on validator uncertainty |

## Structural-failure rationale

The matrix maps structural contract failure to `ERROR` because the exact
supported contract cannot be safely established for the candidate instance.

A later implementation gate may refine internal issue classes.

It must not weaken the fail-closed outcome.

## Integrity-failure rationale

The architecture distinguishes:

- missing, malformed, or unverifiable integrity authority -> `ERROR`;
- complete integrity evidence that deterministically mismatches recomputed
  canonical identity material -> `REJECTED`.

This preserves the difference between unavailable validation authority and
established incompatibility.

## Tenant and engagement rationale

A tenant or engagement mismatch is `REJECTED` only when both sides of the
comparison are authoritative and available.

Missing required context is `ERROR`.

Humanize must not convert missing authority into a guessed mismatch or guessed
match.

## Classification rationale

V3.3 validates classification.

It does not define downstream classification transformation.

Missing or ambiguous classification authority is `ERROR`.

A deterministic incompatibility with an authorized consumption context is
`REJECTED`.

The exact Humanize policy surface for contextual classification compatibility
must be separately reviewed before implementation.

## Provenance rationale

The V3.1 consumer contract requires consumption to fail closed when required
provenance is insufficient.

Canonical Stage 9 also treats absent required observation provenance as
`ERROR`.

This matrix therefore distinguishes:

- unavailable, malformed, dangling, or ambiguous required provenance ->
  `ERROR`;
- complete provenance evidence that proves incompatibility -> `REJECTED`.

No missing provenance may be synthesized to obtain `VALIDATED`.

## Extension rationale

Canonical NDEB semantics permit unknown optional extension objects to be
preserved without interpretation.

Unsupported required extensions fail closed.

This candidate maps unsupported required extension semantics to `ERROR`
because Humanize cannot safely establish the required meaning.

A future compatibility binding may change that only through separately reviewed
upstream and Humanize authority.

## Issue aggregation

The architecture permits multiple diagnostic issue observations for one
candidate.

However:

```text
ANY_ERROR_CONDITION => FINAL_DISPOSITION=ERROR
NO_ERROR_AND_ANY_REJECTION_CONDITION => FINAL_DISPOSITION=REJECTED
NO_ERROR_AND_NO_REJECTION_AND_ALL_REQUIRED_VALIDATIONS_PASS
  => FINAL_DISPOSITION=VALIDATED
```

This is an architecture rule.

Exact executable issue ordering and serialization remain implementation work.

## Deterministic repeatability

Identical logical candidate content, identical Humanize authorization context,
identical supported binding, and identical canonical validation references must
produce the same logical disposition and issue set.

No model judgment or narrative plausibility may affect the result.

## Consumer action matrix

| Disposition | May enter later Humanize delivery workflow? | May mutate NEXUS? | May authorize export? | May authorize client release? |
| --- | --- | --- | --- | --- |
| `VALIDATED` | Eligible only; later phase authority still required | No | No | No |
| `REJECTED` | No | No | No | No |
| `ERROR` | No | No | No | No |

## Diagnostic non-authority

An issue code, log line, validation ID, or error message does not become
evidence authority.

Diagnostic material must remain subordinate to the authoritative source
contract and the actual validation decision.

## Explicit non-authority

```text
EXECUTABLE_DISPOSITION_ENUM_AUTHORITY=NONE
EXECUTABLE_ISSUE_CODE_AUTHORITY=NONE
API_ERROR_MAPPING_AUTHORITY=NONE
HTTP_STATUS_MAPPING_AUTHORITY=NONE
PERSISTENCE_STATUS_MAPPING_AUTHORITY=NONE
V3_3_IMPLEMENTATION_AUTHORITY=NONE
```

## Final matrix invariant

`VALIDATED` is earned only by complete deterministic validation.

Every unsupported, mismatched, unavailable, ambiguous, or unsafe condition
fails closed as `REJECTED` or `ERROR`.
