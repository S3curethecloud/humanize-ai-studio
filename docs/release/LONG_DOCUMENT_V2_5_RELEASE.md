# V2.5 Long-Document Rewrite Release and Control Freeze

## Release boundary

V2.5 extends the V2 rewrite platform with deterministic long-document
structure detection, section-aware rewrite planning and orchestration,
document-wide factual controls, deterministic reconstruction, isolated
long-document audit persistence, a dedicated V2 API surface, and adversarial
backward-compatibility coverage.

Release branch:

`v2/long-document-structure`

V2.4 release baseline:

`676435cb8567f3700b3c1c61a792aa9499104677`

Implementation increments:

- `0b75fcae332c6e9bd89696b9e893cdd4110b2059` — define long-document domain contracts
- `70325c5a2bd614e902fc71508c7357632d9c1c70` — add deterministic document structure detection
- `07b6d824f5730eade7425a4f5860d954586ad1f6` — add deterministic section rewrite planning
- `27bb25c04384440a2c9c80b32830222ecbabef56` — add section-aware rewrite orchestration
- `0d0d58e31df3b26f4b71ed42dc1bf41425e6cced` — add long-document Claim Lock controls
- `9cb1fec563f679bddb6e0ee3bf0b9412967b2707` — add document reconstruction integrity
- `5791625f5804d3168a7fba0f425e0ee5946fe5a4` — add long-document audit persistence
- `57215469c546660241d86145141adf3b2af106a3` — expose long-document rewrites in V2 API
- `3708e1974d972ba3dc6e3dd88b72500b08451e8e` — harden long-document adversarial compatibility

## Product contract

V2.5 provides a dedicated long-document rewrite path while preserving the
existing V1 and V2 rewrite behavior.

The V2.5 long-document system provides:

- deterministic source structure detection;
- deterministic section identity and ordering;
- deterministic section rewrite planning;
- canonical V1 rewrite execution for rewrite-eligible sections;
- preservation of explicitly preserved sections;
- document-wide Claim Lock validation;
- cross-section protected-term and protected-value consistency checks;
- canonical V1 verification authority;
- deterministic document reconstruction;
- persistence of validated long-document audit evidence;
- a dedicated workspace-scoped V2 HTTP endpoint;
- long-document input up to the frozen long-document domain limit;
- adversarial coverage for source tampering, partial failure, control
  precedence, persistence isolation, and byte-preserving reconstruction.

V2.5 does not redefine the canonical V1 rewrite workflow.

V2.5 does not redefine the frozen V2.3 Claim Lock contract.

V2.5 does not merge long-document rewriting with the V2.4 multi-candidate or
Voice DNA request surfaces.

## Long-document domain contract

The long-document domain maximum source length is:

`1,000,000` characters.

A `DocumentStructure` must provide exact full-source coverage.

The section contract requires:

- unique section IDs;
- contiguous section ordinals beginning at one;
- exact source offsets;
- no section gaps;
- no section overlap;
- exact source-text slices;
- final section coverage through the end of the source;
- exact source reconstruction by concatenating section source text.

Section rewrite dispositions are:

- `REWRITE`;
- `PRESERVE`.

A preserved section must remain source-identical.

A `DocumentReconstruction` must contain exactly one result per source section,
in the original order, with exact section identity and source linkage.

## Deterministic structure authority

Structure version:

`document-structure-v1`

Document structure is determined locally and deterministically.

The LLM or rewrite provider is not an authority for:

- section boundaries;
- section identity;
- section order;
- section source offsets;
- whether a section exists.

Markdown ATX headings are the frozen structural signal for V2.5.

When headings are present:

- a preamble before the first heading remains its own section;
- the heading line belongs to the section that it introduces.

When no recognized heading exists, the document is represented as one section.

CRLF and other source bytes represented in the input string remain covered by
the exact source slices.

Structure IDs and section IDs are deterministic.

## Section rewrite planning

Plan version:

`section-rewrite-plan-v1`

Planning is deterministic and provider-free.

A rewrite plan contains exactly one entry for every detected document section.

The plan preserves:

- source section identity;
- source section order;
- contiguous ordinals;
- structure linkage.

A section marked rewrite-ineligible must not be converted into a rewrite
section by downstream orchestration.

V2.5 planning does not permit a model or provider to redefine structural
authority.

## Section-aware rewrite orchestration

Only sections whose plan disposition is `REWRITE` execute through the canonical
V1 rewrite workflow.

Sections whose disposition is `PRESERVE` bypass provider execution and must
remain byte-for-byte source-identical.

The original long-document request is not mutated during section execution.

Every rewritten section must preserve exact source linkage between:

- structure section;
- plan entry;
- section result;
- V1 workflow response.

A workflow response whose reported source text differs from the section source
is an integrity failure.

A V1 workflow response whose verification result is `FAIL` remains an
authoritative failure condition for that section.

Section execution does not reconstruct the complete document.

## V1 verification authority

Canonical V1 verification remains authoritative throughout V2.5.

A section with V1 verification `FAIL` is recorded as a V1-failed section by the
long-document control evaluator.

V1 failure precedence is not replaced by Claim Lock.

If a V1-failed section also has a Claim Lock or cross-section consistency
violation, the existing V1 failure remains authoritative.

A completed reconstructed document must not be produced when authoritative V1
failures remain.

A completed long-document audit must not be persisted when authoritative V1
failures remain.

## Document-wide Claim Lock

V2.5 reuses the frozen V2.3 Claim Lock preparation and validation contracts.

Claim Lock preparation occurs from the original long-document source request.

Claim Lock is evaluated across the ordered section outputs.

Protected claims retain the frozen V2.3 `NOT_EVALUATED` semantics where
applicable.

Protected terms and protected values are evaluated deterministically.

### STRICT

Under `strict` enforcement, a Claim Lock violation fails closed when the
document does not already contain an authoritative V1 failure.

Strict Claim Lock violations do not produce a completed reconstruction or
completed long-document audit.

At the HTTP boundary, controlled strict failures return:

`409 Conflict`

### AUDIT_ONLY

Under `audit_only`, Claim Lock violations are nonblocking.

The completed reconstruction may proceed when no independent authoritative
failure prevents release.

Violation evidence is retained in the long-document audit record.

## Cross-section consistency

V2.5 adds a local deterministic cross-section consistency control for protected
terms and protected values.

The control detects whether an item that existed in a particular source
section remains present in that section's rewritten result.

This is distinct from document-wide Claim Lock validation.

A protected term may remain somewhere in the final document and therefore
satisfy document-wide preservation while still being missing from a source
section in which it originally appeared.

Under `strict`, such a cross-section violation fails closed when no
authoritative V1 failure already takes precedence.

Under `audit_only`, the violation remains nonblocking and is persisted as audit
evidence.

Cross-section consistency does not reinterpret semantic claims and does not
replace canonical V1 verification.

## Reconstruction integrity

Reconstruction occurs only after long-document controls have evaluated the
section execution.

The canonical reconstructed text is the ordered concatenation of section
results.

Reconstruction requires:

- plan structure ID matching the document structure;
- exactly one plan entry per source section;
- exactly one result per source section;
- exact section IDs;
- exact section ordinals;
- exact plan/result disposition linkage;
- exact source-text linkage;
- source-identical output for preserved sections;
- no authoritative V1-failed section IDs.

A missing, reordered, duplicated, tampered, or mismatched section cannot
silently produce a completed document.

Reconstruction does not rerun the rewrite provider.

Reconstruction does not rerun Claim Lock.

## Persistence and audit evidence

Long-document audit version:

`long-document-audit-v1`

V2.5 uses a dedicated long-document audit persistence contract.

The long-document audit record binds:

- workspace ID;
- user ID;
- deterministic document structure;
- deterministic rewrite plan;
- canonical reconstruction;
- Claim Lock validation evidence;
- cross-section consistency evidence;
- authoritative V1 failure linkage;
- creation timestamp.

A completed long-document audit cannot contain authoritative V1-failed section
IDs.

Audit persistence consumes already validated execution and reconstruction
artifacts.

Persistence does not rerun:

- the rewrite workflow;
- structure detection;
- planning;
- Claim Lock validation;
- cross-section evaluation;
- reconstruction.

The audit service verifies reconstruction linkage before persistence.

Both memory and SQLite long-document audit repositories are supported.

SQLite persistence survives service-container recreation.

Long-document audit persistence remains isolated from the existing
single-rewrite history contract.

A completed long-document rewrite therefore does not silently create a legacy
rewrite-history record.

## API exposure

Public endpoint:

`POST /api/v2/workspaces/{workspace_id}/long-document-rewrites`

The endpoint is workspace-scoped.

Workspace membership is required before rewrite execution.

The HTTP orchestration order is:

1. workspace membership;
2. existing Claim Lock preparation;
3. deterministic document structure detection;
4. deterministic section rewrite planning;
5. canonical V1 execution for rewrite sections;
6. long-document control evaluation;
7. deterministic reconstruction;
8. long-document audit persistence;
9. HTTP response.

Expected controlled failure semantics include:

- invalid request shape: `422 Unprocessable Entity`;
- invalid long-document size: `422 Unprocessable Entity`;
- unsupported fields: `422 Unprocessable Entity`;
- workspace membership failure: `403 Forbidden`;
- section execution integrity failure: `409 Conflict`;
- strict Claim Lock violation: `409 Conflict`;
- strict cross-section consistency violation: `409 Conflict`;
- reconstruction integrity failure: `409 Conflict`;
- long-document audit integrity failure: `409 Conflict`.

Expected long-document domain failures must not silently produce successful
completed-document responses.

## Long-document request compatibility

The V2.5 API uses a V2-only long-document rewrite request model.

The V1 `RewriteRequest` production contract remains unchanged.

The long-document endpoint accepts text up to the frozen V2.5 long-document
domain maximum while the existing V1 request contract remains unchanged.

The long-document request rejects unknown fields.

V2.5 intentionally does not accept long-document equivalents of:

- `candidate_count`;
- `voice_profile_id`.

This prevents accidental inference that V2.4 multi-candidate semantics or
Voice DNA semantics automatically apply to long-document rewriting.

Existing:

`POST /api/v2/workspaces/{workspace_id}/rewrites`

behavior remains available and unchanged.

## Adversarial and backward-compatibility coverage

V2.5 adversarial coverage includes:

- rewrite response source mismatch rejection;
- no completed long-document audit after source mismatch;
- later-section V1 failure;
- no partial completed audit after later-section V1 failure;
- strict cross-section protected-term loss;
- document-wide Claim Lock pass combined with strict cross-section failure;
- audit-only cross-section violation persistence;
- exact CRLF reconstruction through API and audit persistence;
- no-heading single-section behavior;
- unknown nested rewrite field rejection;
- invalid Claim Lock mode rejection before workflow execution;
- separation of long-document audit from legacy rewrite history;
- SQLite long-document audit survival after service recreation.

Backward-compatibility validation additionally covers:

- existing base V2 API behavior;
- frozen Claim Lock adversarial behavior;
- frozen multi-candidate adversarial behavior;
- frozen multi-candidate HTTP behavior.

V2.5-I required no production-code correction.

## Known boundaries

V2.5 intentionally does not provide:

- model-determined structural authority;
- arbitrary document-format parsers beyond the frozen V2.5 structure rules;
- semantic section classification by an LLM;
- semantic reinterpretation of canonical V1 factual verification;
- semantic reinterpretation of frozen V2.3 protected claims;
- long-document multi-candidate generation;
- long-document Voice DNA guidance;
- automatic section reordering;
- silent removal of source sections;
- silent recovery from section source mismatch;
- successful reconstruction when a section has authoritative V1 `FAIL`;
- persistence of failed long-document attempts as completed audits;
- persistence of completed long-document rewrites into legacy rewrite history;
- public long-document audit list/get endpoints;
- replacement of the existing V1 control plane;
- replacement of the V2.3 Claim Lock control plane;
- replacement of the V2.4 multi-candidate control plane.

These boundaries define the V2.5 release contract and are not release defects.

## Frozen control surface

The following V2.5 behavior is frozen and requires explicit control review
before weakening or changing it:

- the 1,000,000-character long-document domain maximum;
- exact full-source structure coverage;
- unique and contiguous section identity;
- deterministic structure detection;
- provider-free structural authority;
- deterministic structure IDs and section IDs;
- deterministic section rewrite planning;
- one plan entry per source section;
- preservation of rewrite-ineligible sections;
- canonical V1 workflow execution for rewrite sections;
- source-response integrity checking;
- V1 verification authority;
- V1 failure precedence over Claim Lock;
- document-wide Claim Lock evaluation;
- strict Claim Lock fail-closed behavior;
- audit-only Claim Lock nonblocking behavior;
- local cross-section term/value consistency checking;
- strict cross-section fail-closed behavior;
- audit-only cross-section violation persistence;
- no reconstruction with authoritative V1 failures;
- exact ordered reconstruction;
- preserved-section source identity;
- no silent section deletion or reordering;
- reconstruction linkage integrity;
- isolated long-document audit persistence;
- no completed audit containing authoritative V1 failures;
- workspace-scoped audit access;
- memory and SQLite long-document audit support;
- separation from legacy rewrite history;
- workspace membership before long-document execution;
- dedicated long-document API surface;
- `422` handling for malformed or unsupported request fields;
- controlled `409` handling for expected long-document integrity failures;
- rejection of candidate and Voice DNA fields from the long-document request;
- no V1 behavior changes;
- no V2.3 Claim Lock behavior changes;
- no V2.4 multi-candidate behavior changes.

## Required evidence after frozen-control changes

Any future change to the frozen V2.5 control surface must include:

1. updated long-document domain tests when structural contracts change;
2. updated structure-detector tests when parsing rules change;
3. updated planning tests when rewrite eligibility or plan semantics change;
4. updated section orchestration tests when execution sequencing changes;
5. updated V1-precedence tests when failure semantics change;
6. updated Claim Lock and cross-section tests when factual controls change;
7. updated reconstruction integrity tests when assembly semantics change;
8. updated long-document persistence tests when audit contracts change;
9. updated SQLite tests when storage schema or persistence behavior changes;
10. updated API tests when public request, response, or HTTP failure behavior changes;
11. updated adversarial tests;
12. updated backward-compatibility tests for existing V2 rewrite behavior;
13. updated V2.3 Claim Lock compatibility tests when Claim Lock interaction changes;
14. updated V2.4 multi-candidate compatibility tests when shared API behavior changes;
15. Ruff validation;
16. mypy validation;
17. a passing complete V2 test suite;
18. a passing complete repository/API test suite;
19. `git diff --check` validation;
20. confirmation that protected V1 files were not unintentionally modified;
21. confirmation that the frozen V2.3 Claim Lock release contract was not unintentionally modified;
22. confirmation that the frozen V2.4 release contract was not unintentionally modified;
23. updated release documentation describing the frozen-control change.

## V2.5 release gate

The V2.5 release gate requires:

- Ruff clean;
- mypy clean;
- complete V2 suite passing;
- complete API/repository suite passing;
- V2.5 A–I bounded regression passing;
- V2.5 adversarial suite passing;
- existing V2 API regression passing;
- frozen V2.3 Claim Lock adversarial regression passing;
- frozen V2.4 multi-candidate adversarial regression passing;
- `git diff --check` clean;
- no unintended protected V1 changes;
- no unintended V2.3 Claim Lock changes;
- no unintended V2.4 release-contract changes;
- no unintended changes to frozen V2.5 A–I implementation or test files;
- only the V2.5 release document remaining as an intentional working change
  before the final release/control-freeze commit.

The known Starlette/httpx TestClient deprecation warning is nonblocking for
V2.5 and does not alter long-document behavior.
