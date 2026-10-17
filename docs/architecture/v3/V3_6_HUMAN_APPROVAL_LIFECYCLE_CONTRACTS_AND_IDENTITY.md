# Humanize V3.6 — Contracts and Identity R1

## Contract set

### `ApprovalRequest`

Required fields:
- `tenant_id: str`
- `engagement_id: str`
- `composition_id: str`
- `composition_hash: str`
- `composition_disposition: ELIGIBLE | PRESENTATION_ONLY | BLOCK | ERROR`
- `approval_policy_id: str`
- `approval_policy_hash: str`
- `requested_scope: str`

Rules:
- all identity fields are non-empty;
- `composition_hash` and `approval_policy_hash` are canonical SHA-256 hex strings;
- tenant and engagement are exact-match scope boundaries;
- `BLOCK` and `ERROR` requests are rejected fail-closed before approval aggregation;
- `PRESENTATION_ONLY` may be reviewed, but its V3.5 disposition must remain unchanged.

### `ApproverAuthorityBinding`

Required fields:
- `tenant_id`
- `engagement_id`
- `approver_id`
- `authority_policy_id`
- `authority_policy_hash`
- `allowed_decisions`
- `allowed_requested_scopes`

Rules:
- V3.6 consumes an already validated authority binding;
- V3.6 core performs no provider or IAM lookup;
- tenant and engagement must exactly match the request;
- decision and requested scope must be explicitly authorized;
- authority mismatch returns `ERROR`.

### `ApprovalPolicy`

Required fields:
- `approval_policy_id`
- `approval_policy_hash`
- `required_approver_ids`
- `approval_threshold`

Rules:
- `required_approver_ids` is non-empty, unique, and canonically ordered;
- `approval_threshold >= 1`;
- `approval_threshold <= len(required_approver_ids)`;
- policy identity is immutable input;
- threshold evaluation is deterministic;
- any explicit `REJECT` by an authorized required approver is terminal `REJECTED`;
- any explicit `REQUIRE_REVISION` by an authorized required approver is terminal `REVISION_REQUIRED`.

### `ApprovalDecision`

Required fields:
- `approval_request_id`
- `approver_id`
- `approver_authority_hash`
- `decision: APPROVE | REJECT | REQUIRE_REVISION`
- `reason_code`
- `evidence_hash`

Rules:
- decision must be explicit;
- decision must bind the exact request identity;
- decision must bind the exact approver authority identity;
- identical duplicate evidence is idempotent;
- conflicting decisions from the same approver for one request produce `ERROR`;
- unknown or unauthorized approvers produce `ERROR`.

### `ApprovalResult`

Required fields:
- `approval_request_id`
- `composition_id`
- `composition_hash`
- `source_disposition`
- `approval_state`
- `normalized_decision_ids`
- `approval_trace_hash`
- `failure_codes`

Rules:
- `source_disposition` is preserved exactly from V3.5;
- `approval_state=APPROVED` never changes `source_disposition`;
- authoritative successor eligibility requires both preserved V3.5 semantics and valid V3.6 approval, interpreted by a later capability.

## Deterministic identity

### Approval request identity

`approval_request_id = SHA256(canonical(request identity fields))`

Identity fields:
- tenant
- engagement
- composition id
- composition hash
- source disposition
- approval policy id
- approval policy hash
- requested scope

### Approver authority identity

`approver_authority_hash = SHA256(canonical(authority binding))`

### Decision identity

`approval_decision_id = SHA256(canonical(decision fields))`

Decision identity excludes wall-clock time and provider-specific metadata.

### Approval trace identity

`approval_trace_hash = SHA256(canonical(request identity + policy identity + normalized decision identities + final state + failure codes))`

## Canonicalization

- UTF-8;
- explicit field names;
- stable key ordering;
- no insignificant whitespace;
- normalized decision list ordering by `(approver_id, approval_decision_id)`;
- duplicate identical decisions collapse idempotently;
- no locale-sensitive transforms;
- no process-specific object representation.

## Time metadata

External timestamps may be retained only as non-authoritative audit metadata by a later integration layer. Core V3.6 approval semantics and identities do not depend on current time or mutable clock reads.
