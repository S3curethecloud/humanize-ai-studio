# Humanize V3.7 - Delivery Manifest Contracts and Identity R1

## Status

Detached architecture planning candidate only. All names below are planning-level contract names. No runtime type, schema, API, persistence object, or repository path is authorized by this document.

## `ArtifactDescriptor`

Required semantic fields:

- `artifact_id`
- `artifact_version`
- `artifact_sha256`
- `artifact_kind`
- `source_composition_id`
- `source_composition_hash`

Rules:

- identity fields are non-empty;
- `artifact_sha256` is canonical lowercase SHA-256 hex;
- artifact version is explicit and non-empty;
- source composition identity/hash must match the approved V3.5/V3.6 source binding;
- artifact identity/version pairs are unique within one manifest subject;
- an identical duplicate descriptor may collapse idempotently;
- conflicting descriptors for the same artifact identity/version fail closed.

## `ApprovalBinding`

V3.7 must not redefine approval. It carries an exact binding to accepted V3.6 output.

Required semantic fields:

- `approval_request_id`
- `approval_trace_hash`
- `approval_state`
- `composition_id`
- `composition_hash`
- `source_disposition`

Rules:

- `approval_state` must be the exact V3.6 state;
- export eligibility requires `approval_state=APPROVED`;
- V3.7 never converts `PENDING`, `REJECTED`, `REVISION_REQUIRED`, or `ERROR` into approval;
- the binding must match the exact composition used by every artifact descriptor;
- `source_disposition` remains preserved and may be evaluated by explicit export policy, but is never promoted by V3.7.

## `GenerationMetadata`

Candidate deterministic fields:

- `generator_id`
- `generator_version`
- `generation_profile_id`
- `generation_profile_hash`

Rules:

- metadata that participates in manifest identity must be deterministic and explicitly supplied;
- current time, host name, PID, random values, temporary paths, and provider response metadata must not participate in core manifest identity;
- optional external audit timestamps may be carried by a later integration layer as non-authoritative metadata and must not alter deterministic authorization semantics.

## `DeliveryManifestSubject`

Required semantic fields:

- `tenant_id`
- `engagement_id`
- `package_id`
- `artifacts`
- `source_bundle_id`
- `source_bundle_version`
- `provenance_refs`
- `classification`
- `approval_binding`
- `generation_metadata`

The manifest subject intentionally excludes the export decision to avoid circular identity.

### Package identity

Candidate deterministic rule:

`package_id = "package:sha256:" + SHA256(canonical(package subject fields))`

Package subject fields include:

- tenant;
- engagement;
- source bundle identity/version;
- normalized artifact identities/versions/hashes;
- normalized provenance references;
- classification;
- approval request identity and approval trace hash;
- deterministic generation profile identity/hash.

### Manifest-subject identity

`manifest_subject_hash = SHA256(canonical(DeliveryManifestSubject))`

Candidate external identity form:

`manifest-subject:sha256:<64 lowercase hex>`

## `ExportAuthorizationPolicy`

Planning-level semantic fields:

- `export_policy_id`
- `export_policy_hash`
- `allowed_classifications`
- `allowed_source_dispositions`
- `allowed_audiences`
- `allowed_delivery_contexts`
- `required_approval_states`

Rules:

- policy identity is explicit immutable input;
- allowed sets are unique and canonically ordered;
- missing/unknown policy identity fails closed;
- policy may restrict or deny export but may not rewrite upstream classification, approval, provenance, or source truth;
- provider lookup is outside the provider-free core.

## `ExportAuthorizationRequest`

Required semantic fields:

- `tenant_id`
- `engagement_id`
- `manifest_subject_hash`
- `artifact_ids_and_versions`
- `classification`
- `approval_request_id`
- `approval_trace_hash`
- `approval_state`
- `source_disposition`
- `intended_audience`
- `allowed_delivery_context`
- `export_policy_id`
- `export_policy_hash`

Rules:

- request binds one exact manifest subject;
- request tenant/engagement must exactly match the manifest subject;
- request artifact set must exactly equal the manifest subject artifact set;
- request classification must exactly bind the manifest classification;
- request approval binding must exactly equal the manifest approval binding;
- request audience and delivery context must be explicit, non-empty, and policy permitted;
- request identity changes whenever any authorization-relevant field changes.

### Export request identity

`export_request_id = SHA256(canonical(ExportAuthorizationRequest))`

Candidate external identity form:

`export-request:sha256:<64 lowercase hex>`

## `ExportAuthorizationDecision`

Candidate decision states:

- `AUTHORIZED`
- `DENIED`
- `ERROR`

Required semantic fields:

- `export_request_id`
- `manifest_subject_hash`
- `decision`
- `export_policy_id`
- `export_policy_hash`
- `normalized_failure_codes`
- `export_trace_hash`

Rules:

- `AUTHORIZED` means only that the exact manifest subject is authorized for the exact intended audience and allowed delivery context under the exact supplied policy;
- `AUTHORIZED` does not mean client released;
- policy refusal yields `DENIED`;
- malformed, contradictory, stale, cross-tenant, or authority-invalid evidence yields `ERROR`;
- decision is deterministic for an exact input set.

### Export decision identity

`export_decision_id = SHA256(canonical(export request identity + policy identity + decision + failure codes + export trace hash))`

## `DeliveryManifest`

The final manifest records the exact manifest subject plus the exact export decision.

Required semantic fields include the canonical roadmap content:

- tenant;
- engagement;
- package identity;
- artifact identities;
- artifact hashes;
- source bundle identity;
- source bundle version;
- provenance references;
- classification;
- approvals;
- export decision;
- generation metadata.

Additional binding fields may include:

- `manifest_subject_hash`
- `export_request_id`
- `export_decision_id`
- `export_trace_hash`

### Final manifest identity

`delivery_manifest_id = "delivery-manifest:sha256:" + SHA256(canonical(final manifest fields))`

The final manifest identity is computed only after export decision identity is fixed.

## Canonical ordering

- UTF-8;
- explicit field names;
- stable key ordering;
- no insignificant whitespace in canonical identity serialization;
- artifacts ordered by `(artifact_id, artifact_version, artifact_sha256)`;
- provenance references unique and lexicographically ordered;
- allowed policy sets unique and lexicographically ordered;
- failure codes unique and lexicographically ordered;
- no locale-sensitive transforms;
- no process-specific object representations.

## Identity versus authority

SHA-256 identities prove deterministic binding of supplied data. They do not create source truth, human approval, export authority, or client-release authority.
