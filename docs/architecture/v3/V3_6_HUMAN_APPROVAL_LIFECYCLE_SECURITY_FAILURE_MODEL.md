# Humanize V3.6 — Security and Failure Model R1

## Security objective

The Human Approval Lifecycle must ensure that explicit human judgment is bound to the exact governed composition being reviewed, by an exact authorized approver scope, without weakening any V3.5 protection.

## Threats and required response

### Cross-tenant approval injection
Threat: a valid decision from tenant A is presented for tenant B.
Response: exact tenant mismatch -> `ERROR`.

### Cross-engagement approval injection
Threat: an approval for one engagement is reused in another.
Response: exact engagement mismatch -> `ERROR`.

### Composition substitution
Threat: an approval for composition X is reused after content changes to composition Y.
Response: composition id/hash mismatch -> `ERROR`; new request required.

### Provenance laundering
Threat: approval is used to rewrite or hide V3.5 provenance.
Response: prohibited by contract; V3.5 authority/provenance trace is immutable input and preserved output trace.

### Classification/disposition escalation
Threat: human approval upgrades `BLOCK`, `ERROR`, or `PRESENTATION_ONLY`.
Response:
- `BLOCK` and `ERROR` fail closed before approval;
- `PRESENTATION_ONLY` remains presentation-only even if human-review state is `APPROVED`.

### Unauthorized approver
Threat: decision is submitted by a subject outside the bound authority policy.
Response: `ERROR`.

### Decision replay
Threat: old decision is replayed against a changed request.
Response: request identity mismatch -> `ERROR`.

### Conflicting human decisions
Threat: one approver submits different decisions for the same request.
Response: `ERROR`, never last-write-wins.

### Missing human decision
Threat: system treats absence as approval.
Response: `PENDING`.

### Threshold manipulation
Threat: caller changes policy or approver set while keeping old approval evidence.
Response: policy identity is part of request identity; mismatch creates a distinct request or `ERROR`.

### Clock manipulation
Threat: host clock changes approval semantics.
Response: core semantics use no current-time reads.

### Provider/IAM ambiguity
Threat: core behavior changes according to external provider state.
Response: core consumes explicit immutable authority bindings; provider lookup belongs outside V3.6 core.

## Failure characteristics

- fail closed;
- deterministic;
- no silent conflict resolution;
- no implicit authority;
- no partial authoritative output on structural or authority error;
- no mutation of V3.5 composition;
- no network, provider, persistence, rendering, or export side effects.

## Audit trace requirements

The approval trace must preserve:
- V3.5 composition identity and hash;
- source disposition;
- approval request identity;
- approval policy identity;
- normalized approver authority identities;
- normalized decision identities;
- final approval state;
- explicit failure codes;
- deterministic trace hash.

The trace proves what was approved, by whom under which supplied authority binding, and under which deterministic policy semantics. It does not claim that V3.6 itself authenticated an external identity provider.
