# Humanize V3.7 - Security and Failure Model R1

## Status

Detached architecture planning candidate only.

## Security objective

V3.7 must ensure that export authorization is bound to one exact tenant/engagement package state, exact artifacts, exact hashes, exact source evidence/provenance/classification, exact V3.6 approval evidence, exact audience, exact delivery context, and exact export policy without granting client-release authority.

## Threats and required response

### Cross-tenant package injection

Threat: a manifest subject or artifact from tenant A is presented for tenant B.

Required response: exact tenant mismatch -> `ERROR`.

### Cross-engagement package injection

Threat: evidence or artifacts from one engagement are reused in another.

Required response: exact engagement mismatch -> `ERROR`.

### Artifact substitution

Threat: an authorized artifact identity is paired with different bytes.

Required response: artifact hash mismatch -> `ERROR`; prior decision is stale.

### Artifact version substitution

Threat: a decision for version N is replayed for version N+1.

Required response: version mismatch changes the request identity; old decision cannot authorize the new version.

### Conflicting artifact identity

Threat: two non-identical descriptors claim the same artifact identity/version.

Required response: `ERROR`, never last-write-wins.

### Manifest substitution

Threat: a decision for one manifest subject is attached to another.

Required response: manifest-subject hash mismatch -> `ERROR`.

### Circular manifest identity

Threat: final manifest identity is used as authorization input while it also contains the authorization decision.

Required response: prohibited architecture. Authorization binds the pre-decision `manifest_subject_hash`; final manifest identity is computed afterward.

### Stale human approval

Threat: an approval for old composition content is reused after the source or artifact changes.

Required response: exact V3.6 composition/request/hash mismatch -> `ERROR`; new approval or exact rebinding is required by upstream authority.

### Approval laundering

Threat: V3.7 treats artifact existence or a generated manifest as equivalent to V3.6 approval.

Required response: explicit V3.6 `APPROVED` binding is required; absence -> `DENIED` or `ERROR` according to structural validity.

### Provenance stripping

Threat: generated package omits or replaces authoritative provenance references.

Required response: missing or contradictory required provenance -> `ERROR`.

### Classification downgrade

Threat: export request silently weakens source classification.

Required response: `ERROR` for inconsistent binding; policy may apply stricter handling but never silently downgrade authoritative source classification.

### Audience confusion

Threat: authorization for one audience is replayed for another.

Required response: audience is part of request identity; changed audience requires a new decision.

### Delivery-context confusion

Threat: authorization for one destination/context is reused for another.

Required response: delivery context is part of request identity; mismatch -> stale decision / new request required.

### Export-policy substitution

Threat: policy contents change while an old policy identity/hash or decision is reused.

Required response: policy hash mismatch -> `ERROR`; new request/decision required.

### Provider/IAM ambiguity

Threat: core behavior varies with external provider state or IAM lookup.

Required response: provider-free core consumes explicit immutable policy/authority bindings; provider lookup remains outside core V3.7 semantics.

### Generation-metadata injection

Threat: volatile host/process/time metadata changes manifest identity nondeterministically.

Required response: identity-participating generation metadata is limited to explicit deterministic inputs; volatile audit metadata remains outside core identity.

### Clock manipulation

Threat: current host time changes export decision semantics.

Required response: core evaluation uses no current-time reads.

### Client-release escalation

Threat: `AUTHORIZED` is interpreted as proof that the client received the artifact.

Required response: prohibited. Export authorization and client release remain separate authorities and separate evidence events.

### NEXUS truth rewriting

Threat: Humanize manifest content is treated as new architecture/evidence truth.

Required response: manifest preserves references to authoritative upstream evidence; Humanize does not become source authority.

## Fail-closed characteristics

- structural invalidity -> `ERROR`;
- authority ambiguity -> `ERROR`;
- contradictory identity -> `ERROR`;
- stale binding -> `ERROR`;
- policy refusal -> `DENIED`;
- missing approval -> not authorized;
- no implicit success;
- no last-write-wins conflict resolution;
- no partial authoritative export result on `ERROR`;
- no mutation of predecessor evidence;
- no network/provider/persistence/render/release side effects in provider-free core semantics.

## Audit/evidence trace requirements

The V3.7 trace must preserve at least:

- tenant and engagement;
- package identity;
- manifest-subject hash;
- final manifest identity/hash when constructed;
- normalized artifact identities, versions, and hashes;
- source bundle identity/version;
- provenance references;
- classification;
- V3.6 approval request identity and trace hash;
- source disposition;
- intended audience;
- delivery context;
- export policy identity/hash;
- export request identity;
- export decision;
- failure codes;
- export decision identity and trace hash.

The trace proves what exact package state was evaluated under what supplied policy. It does not prove external transmission or client receipt.
