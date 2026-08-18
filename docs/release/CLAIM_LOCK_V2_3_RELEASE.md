# V2.3 Claim Lock Release and Control Freeze

## Release boundary

V2.3 Claim Lock extends the V2 rewrite platform with deterministic protection
for terminology and literal values while preserving the existing V1 factual
verification authority.

Release branch:

`v2/claim-lock-domain`

Implementation increments:

- `585a9c6` — define Claim Lock domain contracts
- `b04affb` — add deterministic Claim Lock extraction
- `d197bb9` — add deterministic protected claim extraction
- `2755974` — integrate Claim Lock preparation into rewrites
- `d25c1c6` — enforce post-generation Claim Lock policy
- `e5f98b5` — persist Claim Lock history audit contract
- `7bc142c` — persist Claim Lock audit evidence in SQLite
- `362dd9d` — expose Claim Lock controls and evidence in the V2 API
- `b03690a` — add adversarial Claim Lock coverage

## Product contract

Claim Lock protects rewrite inputs that must not be altered during generation.

The V2 API supports:

- explicit protected terminology through `protected_terms`;
- `strict` and `audit_only` enforcement modes;
- deterministic extraction of protected literal values;
- post-generation validation evidence;
- persisted Claim Lock audit evidence;
- Voice DNA rewrites subject to the same Claim Lock controls.

Existing V2 callers remain backward-compatible when they do not explicitly
request Claim Lock controls.

## Frozen enforcement semantics

### STRICT

`strict` enforcement fails closed when a deterministically evaluated protected
term or protected value is missing from the rewritten output and the canonical
V1 verification result is not already `FAIL`.

At the HTTP boundary, this condition returns `409 Conflict`.

A strict Claim Lock violation is not recorded as a completed rewrite-history
record.

### AUDIT_ONLY

`audit_only` enforcement does not block completion.

A deterministic violation is returned in Claim Lock validation evidence and is
persisted with rewrite history for auditability.

### V1 verification authority

Claim Lock does not supersede or reinterpret the canonical V1 factual
verification result.

When V1 verification returns `FAIL`, that V1 result remains authoritative.
Claim Lock must not replace the V1 failure with a separate Claim Lock outcome.

This precedence is part of the frozen V2.3 control contract.

## Protected terms

Protected terms are evaluated deterministically against rewritten output.

- Case-sensitive terms require exact case-preserving presence.
- Case-insensitive terms use case-insensitive matching.
- A missing protected term produces a Claim Lock validation violation.
- Claim Lock does not silently normalize or substitute protected terminology.

## Protected values

Protected values use exact-literal preservation.

Covered deterministic value classes include:

- numbers;
- percentages;
- dates;
- URLs;
- identifiers;
- codes.

Mutation of an extracted protected literal is a deterministic Claim Lock
violation.

V2.3 does not claim semantic equivalence between alternate representations of
the same value.

## Protected claims

Protected claims are extracted and included in Claim Lock evidence, but V2.3
does not claim deterministic semantic claim-preservation evaluation.

Claim validation status is therefore:

`not_evaluated`

for semantic protected claims.

This is intentional. Legitimate paraphrases must not be rejected merely
because the source claim is no longer present as an exact string.

Semantic claim preservation continues to rely on the canonical V1 factual
verification controls.

## Voice DNA interaction

Voice DNA is subordinate to factual-preservation and Claim Lock controls.

Voice guidance may affect style, tone, and presentation, but it cannot override
protected terminology, protected values, V1 verification, or Claim Lock
enforcement.

A Voice DNA rewrite that violates a strict deterministic Claim Lock receives
the same failure behavior as a non-voice rewrite.

## Persistence and audit evidence

Completed Claim Lock-enabled rewrites can persist:

- the Claim Lock snapshot;
- Claim Lock validation evidence;
- the enforcement mode.

The history contract requires these Claim Lock audit fields to be either all
present or all absent.

When present:

- snapshot and validation lock IDs must match;
- snapshot enforcement mode must match the persisted enforcement mode;
- validation enforcement mode must match the persisted enforcement mode.

SQLite supports additive migration of the Claim Lock history columns and
round-trip deserialization.

Historical rewrite records created before Claim Lock remain readable with the
Claim Lock audit fields absent.

## Adversarial release coverage

The V2.3 adversarial suite covers:

- protected-term mutation;
- case-only protected-term mutation;
- numeric drift;
- percentage drift;
- date drift;
- URL drift;
- identifier drift;
- code drift;
- exact protected-value preservation;
- strict API failure semantics;
- audit-only violation evidence;
- audit-only history persistence;
- Voice DNA plus strict Claim Lock enforcement.

## Known boundaries

V2.3 intentionally does not provide:

- deterministic semantic equivalence evaluation for protected claims;
- detection of every newly introduced value that did not exist in source text;
- semantic normalization of alternate date, numeric, URL, or identifier forms;
- persistence of failed strict Claim Lock attempts as completed history;
- replacement of the V1 factual verification control plane.

These are not release defects. They define the V2.3 feature boundary.

## Frozen control surface

The following V2.3 behavior is frozen and requires explicit control review
before weakening or changing it:

- STRICT fail-closed behavior for deterministic violations;
- AUDIT_ONLY evidence persistence;
- V1 verification precedence;
- exact-literal protected-value validation;
- protected-term case-sensitivity behavior;
- semantic claims remaining `not_evaluated`;
- Voice DNA subordination to Claim Lock;
- Claim Lock history tuple integrity;
- SQLite backward-compatible migration behavior;
- opt-in backward compatibility for the V2 rewrite API;
- HTTP `409 Conflict` semantics for strict Claim Lock violations.

## Required evidence after frozen-control changes

Any future change to the frozen Claim Lock control surface must include:

1. updated unit and adversarial tests;
2. updated persistence tests when audit contracts change;
3. updated API tests when request, response, or failure semantics change;
4. Ruff validation;
5. mypy validation;
6. a passing complete V2 test suite;
7. a passing complete repository test suite;
8. confirmation that protected V1 files were not unintentionally modified;
9. updated release documentation describing the control change.

## V2.3 release gate

The release gate requires:

- Ruff clean;
- mypy clean;
- complete V2 suite passing;
- complete repository suite passing;
- `git diff --check` clean;
- no unintended protected V1 changes;
- only intentional release-evidence changes remaining before the release
  evidence commit.

The known Starlette/httpx TestClient deprecation warning is nonblocking for
V2.3 and does not alter Claim Lock behavior.
