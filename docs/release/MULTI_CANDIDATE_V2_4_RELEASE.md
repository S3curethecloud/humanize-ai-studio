# V2.4 Multi-Candidate Rewrite Release and Control Freeze

## Release boundary

V2.4 extends the V2 rewrite platform with optional multi-candidate generation,
deterministic visual diff evidence, per-candidate safety controls,
deterministic ranking and selection, persisted candidate audit evidence, and a
backward-compatible V2 API surface.

Release branch:

`v2/multi-candidate-diff`

Implementation increments:

- `f09d3f0` — define multi-candidate rewrite and diff contracts
- `c6cbdd9` — add deterministic candidate visual diff engine
- `108407c` — add deterministic candidate generation orchestration
- `40cfdc7` — enforce V1 and Claim Lock controls per candidate
- `c663b9f` — add deterministic candidate ranking and selection
- `a568acc` — persist candidate selection audit evidence
- `7b9e2b3` — expose optional multi-candidate rewrite API
- `e36acdf` — harden multi-candidate adversarial boundaries

## Product contract

V2.4 allows a caller to request multiple rewrite candidates while preserving
the existing single-result V2 contract by default.

The V2 API supports:

- optional multi-candidate generation through `candidate_count`;
- between two and five candidates per requested candidate set;
- deterministic candidate-generation strategies;
- deterministic lossless visual diff evidence;
- canonical V1 verification for every candidate;
- Claim Lock validation for every candidate;
- deterministic candidate ranking and selection;
- persisted candidate-selection audit evidence;
- optional Voice DNA guidance subject to the same safety controls;
- a selected rewrite returned through the existing `rewrite` response field;
- additional multi-candidate evidence only when explicitly requested.

Existing V2 callers that omit `candidate_count`, or explicitly provide
`candidate_count: null`, remain on the existing single-result rewrite path.

V1 behavior is unchanged.

## Candidate generation

Candidate generation is bounded to two through five candidates.

Each candidate is generated from the same original rewrite request with a
deterministic candidate-generation directive applied to the request tone used
for that candidate execution.

The caller's original request object and persisted request contract are not
mutated by candidate-generation directives.

Candidate ordinals are contiguous and ordered from one.

Candidate IDs and candidate-set IDs are deterministic outputs of the candidate
planning contract.

Candidate generation fails closed when:

- a candidate workflow response reports source text different from the
  original request source text;
- two generated candidates produce identical rewritten output.

These conditions are candidate-generation integrity failures.

At the HTTP boundary they return `409 Conflict`.

## Visual diff contract

The V2.4 visual diff engine is deterministic.

Diff version:

`candidate-diff-v1`

Diff construction uses lossless tokenization and deterministic sequence
comparison between the original source and each candidate.

Each candidate diff must reconstruct:

- the exact original source from source-side segments;
- the exact candidate output from candidate-side segments.

Supported diff operations are:

- `equal`;
- `insert`;
- `delete`;
- `replace`.

Visual diff evidence is explanatory evidence only.

Diff results do not override V1 factual verification, Claim Lock validation,
candidate eligibility, or release decisions.

## Per-candidate control enforcement

Every candidate passes through the canonical V1 rewrite workflow.

Every candidate therefore receives the canonical V1 verification and
editorial-quality controls before selection.

Claim Lock preparation is performed from the original source request and the
same prepared Claim Lock is evaluated against each candidate.

Voice DNA does not bypass V1 or Claim Lock controls.

## Claim Lock precedence

V2.4 preserves the frozen V2.3 Claim Lock semantics.

### STRICT

Under `strict` Claim Lock enforcement, a deterministic Claim Lock violation on
a candidate whose V1 verification result is not already `FAIL` aborts the
multi-candidate rewrite.

The system must not silently discard the violating candidate and select another
candidate to bypass strict enforcement.

At the HTTP boundary this condition returns `409 Conflict`.

A failed strict multi-candidate attempt is not persisted as a completed rewrite
history record.

### AUDIT_ONLY

Under `audit_only`, a Claim Lock violation does not abort candidate generation.

The violating candidate remains eligible for ranking unless another independent
control makes it ineligible.

A clean Claim Lock candidate ranks ahead of an otherwise comparable
audit-only violating candidate according to the deterministic ranking contract.

Violation evidence is retained in candidate audit evidence.

### V1 verification authority

V1 verification remains authoritative.

A candidate with V1 verification `FAIL` is ineligible for selection.

When a V1-failed candidate also contains a Claim Lock violation, the existing V1
failure remains authoritative and the Claim Lock condition does not replace it
with a separate strict-failure outcome.

This preserves the frozen V2.3 control precedence.

## Deterministic ranking and selection

Ranking version:

`candidate-ranking-v1`

Candidate ranking is deterministic.

Eligibility rules:

- V1 `FAIL` candidates are ineligible;
- strict Claim Lock violating candidates are ineligible where applicable;
- audit-only Claim Lock violating candidates remain eligible.

Eligible candidate ordering uses the following precedence:

1. V1 `PASS` before V1 `WARN`;
2. clean Claim Lock result before audit-only Claim Lock violation;
3. editorial-quality `PASS` before editorial review outcomes;
4. higher editorial naturalness score;
5. fewer remaining editorial flags;
6. fewer changed diff segments;
7. lower candidate ordinal as the final deterministic tie-break.

The selected candidate must be rank one among eligible candidates.

If no candidate is eligible, selection fails closed.

At the HTTP boundary, no eligible candidate returns `409 Conflict`.

No completed rewrite history is persisted for a no-eligible-candidate failure.

## Persistence and audit evidence

Candidate audit version:

`candidate-audit-v1`

Completed multi-candidate rewrites persist the selected rewrite through the
existing rewrite-history contract.

Candidate-aware history additionally links:

- `candidate_set_id`;
- candidate audit snapshot;
- `selected_candidate_id`.

The candidate audit snapshot includes:

- candidate control evidence;
- V1 release decision per candidate;
- Claim Lock validation evidence per candidate;
- deterministic ranking and selection evidence;
- selected-candidate linkage.

Candidate history linkage is coherent as an all-or-none audit contract.

When candidate audit evidence is present:

- history candidate-set ID must match the audit snapshot candidate-set ID;
- selected candidate ID must match the audit snapshot selected candidate ID;
- audit control candidate IDs must match ranking candidate IDs;
- audit candidate ordinals must remain contiguous and ordered.

SQLite supports additive candidate-audit history columns and backward-compatible
reads of historical records created before V2.4.

Legacy history records remain readable with candidate audit fields absent.

## API compatibility

Multi-candidate rewriting is an opt-in V2 capability.

Public request field:

`candidate_count`

Accepted non-null values:

`2` through `5`

Omitted `candidate_count` preserves the existing V2 single-result path.

Explicit `candidate_count: null` also preserves the existing V2 single-result
path.

Malformed or out-of-range candidate counts are rejected by request validation
with `422 Unprocessable Entity`.

When multi-candidate rewriting is not requested:

- `multi_candidate` is absent from the serialized response;
- candidate history linkage fields remain absent from serialized legacy
  history responses;
- existing single-result Voice DNA and Claim Lock behavior remains unchanged.

When multi-candidate rewriting is requested, the response exposes:

- candidate set;
- visual diffs;
- per-candidate control evidence;
- deterministic selection evidence;
- candidate audit snapshot.

The existing top-level `rewrite` field remains the selected candidate rewrite,
preserving the existing selected-result consumption pattern.

## HTTP failure semantics

The V2.4 multi-candidate HTTP boundary uses controlled failures for expected
domain conditions.

- invalid request shape or candidate count: `422 Unprocessable Entity`;
- workspace membership failure: `403 Forbidden`;
- strict Claim Lock violation: `409 Conflict`;
- no eligible candidate: `409 Conflict`;
- candidate-generation source mismatch: `409 Conflict`;
- duplicate candidate output integrity failure: `409 Conflict`;
- unavailable Voice DNA multi-candidate orchestration:
  `503 Service Unavailable`.

Expected candidate-generation integrity failures must not escape as uncontrolled
`500 Internal Server Error` responses.

## Voice DNA interaction

Voice DNA remains subordinate to factual preservation and Claim Lock.

When a voice profile is requested for multi-candidate generation:

- voice guidance applies to candidate generation;
- V1 verification still evaluates every candidate;
- Claim Lock still evaluates every candidate;
- voice guidance cannot grant candidate eligibility;
- voice guidance cannot override strict Claim Lock;
- voice guidance cannot override a V1 `FAIL`.

If the multi-candidate service cannot provide the required voice-aware
orchestration, the request fails with `503 Service Unavailable`.

## Adversarial release coverage

V2.4 adversarial coverage includes:

- duplicate candidate output rejection;
- candidate source-text mismatch rejection;
- zero completed history after candidate-generation failure;
- zero partial candidate audit after candidate-generation failure;
- strict Claim Lock violation aborting the entire candidate set;
- V1-failed plus Claim Lock-violating candidate precedence;
- audit-only Claim Lock violation remaining nonblocking;
- clean candidate ranking ahead of an audit-only violating candidate;
- all candidates receiving V1 `FAIL`;
- no eligible candidate fail-closed behavior;
- original request immutability during candidate generation;
- malformed candidate-count request validation;
- omitted candidate-count backward compatibility;
- explicit-null candidate-count backward compatibility;
- Claim Lock behavior on the legacy single-result path;
- real workspace membership enforcement on the multi-candidate path;
- controlled HTTP handling for duplicate candidate generation;
- controlled HTTP handling for candidate source mismatch.

## Known boundaries

V2.4 intentionally does not provide:

- more than five candidates in a candidate set;
- stochastic ranking or model-based candidate judging;
- semantic reinterpretation of the canonical V1 verification result;
- semantic reinterpretation of V2.3 Claim Lock protected claims;
- automatic recovery from duplicate candidate outputs;
- silent fallback to another candidate after a strict Claim Lock violation;
- persistence of failed candidate-generation attempts as completed history;
- persistence of no-eligible-candidate attempts as completed history;
- replacement of the existing V1 factual verification control plane;
- replacement of the V2.3 Claim Lock control plane.

These boundaries define the V2.4 release contract and are not release defects.

## Frozen control surface

The following V2.4 behavior is frozen and requires explicit control review
before weakening or changing it:

- multi-candidate generation remaining opt-in;
- two-to-five candidate request bounds;
- omitted and null `candidate_count` preserving the legacy single-result path;
- deterministic candidate planning;
- source-text integrity enforcement for every candidate;
- duplicate rewritten-output rejection;
- deterministic lossless visual diff behavior;
- canonical V1 workflow execution for every candidate;
- V1 `FAIL` candidate ineligibility;
- V1 verification precedence over Claim Lock;
- strict Claim Lock fail-closed behavior across the entire candidate set;
- audit-only Claim Lock remaining nonblocking;
- deterministic ranking order;
- no-eligible-candidate fail-closed behavior;
- selected candidate matching rank one;
- candidate audit linkage integrity;
- selected rewrite persistence through the existing history contract;
- no completed history after failed generation or failed strict enforcement;
- Voice DNA subordination to V1 and Claim Lock;
- HTTP `409 Conflict` handling for candidate-generation integrity failures;
- backward-compatible V2 response shape when multi-candidate mode is not
  requested;
- no V1 behavior changes.

## Required evidence after frozen-control changes

Any future change to the frozen V2.4 control surface must include:

1. updated domain and service tests;
2. updated adversarial tests;
3. updated API compatibility and negative-path tests;
4. updated persistence tests when candidate audit contracts change;
5. updated SQLite migration tests when persistence schema changes;
6. updated Voice DNA interaction tests when voice behavior changes;
7. updated Claim Lock tests when candidate enforcement semantics change;
8. Ruff validation;
9. mypy validation;
10. a passing complete V2 test suite;
11. a passing complete repository test suite;
12. `git diff --check` validation;
13. confirmation that protected V1 files were not unintentionally modified;
14. confirmation that the frozen V2.3 Claim Lock release contract was not
    unintentionally modified;
15. updated release documentation describing the control change.

## V2.4 release gate

The V2.4 release gate requires:

- Ruff clean;
- mypy clean;
- complete V2 suite passing;
- complete repository suite passing;
- `git diff --check` clean;
- no unintended protected V1 changes;
- no unintended V2.3 Claim Lock release-contract changes;
- only intentional V2.4 release-evidence changes remaining before the final
  release-evidence commit.

The known Starlette/httpx TestClient deprecation warning is nonblocking for
V2.4 and does not alter multi-candidate behavior.
