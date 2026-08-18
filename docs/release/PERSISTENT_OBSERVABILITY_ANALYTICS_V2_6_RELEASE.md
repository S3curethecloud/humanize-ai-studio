# V2.6 Persistent Observability and Analytics Release and Control Freeze

## Release boundary

V2.6 extends the V2 platform with persistent, workspace-scoped observability
and deterministic analytics while preserving the existing canonical V1
rewrite workflow, V2 rewrite/history authority, Claim Lock controls,
multi-candidate controls, long-document controls, and existing rewrite
execution semantics.

Release branch:

`v2/persistent-observability-analytics`

V2.5 release baseline:

`04ede62b0bc0acbb923b4f0a59f897c018b43e23`

Implementation increments:

- `a38af96d03dd3b91f2ef1bd6c621dbc204cbbe45` — define persistent observability contracts
- `4ecdff69d80bca5113b05a0e17252891f953fc62` — add persistent observability repositories
- `f5cd247b97bb70994b61b3738102d0a62e458d7e` — add persistent observability recording service
- `98e4e72e3cc07de85743253fb56e3ab5858378db` — instrument single rewrites with persistent observability
- `fcc545b260b6e2f75a673436ccd47671e1791c51` — instrument complex rewrites with persistent observability
- `c1b95035be5c8c20c666f304e4ab1f2bc4317ca0` — add deterministic workspace analytics aggregation
- `b6c7b2c8d3c29bc18e065624dea976b9c9cd3ec3` — add persistent workspace analytics query service
- `f0978809b4c2f0ac3eacb9c2ecd01edf0835259d` — expose workspace analytics and secure metrics
- `0a2438fb6d1ed38bde8759d94e2e3787eb14b9d5` — harden observability restart and compatibility

## Product contract

V2.6 provides persistent observability for completed V2 rewrite operations and
workspace-scoped deterministic analytics over those persisted events.

V2.6 provides:

- frozen persistent observability event contracts;
- content-minimized telemetry that excludes raw rewrite text and prompts;
- memory and SQLite observability repositories;
- exact-once recording attempts at the recording-service boundary;
- validation before persistence mutation;
- no silent persistence retries;
- fail-closed repository-result integrity checking;
- completed single-rewrite instrumentation;
- completed multi-candidate instrumentation;
- completed long-document instrumentation;
- deterministic workspace analytics aggregation;
- workspace-authorized analytics queries;
- fail-closed analytics truncation detection;
- a workspace-scoped analytics HTTP endpoint;
- an explicit authorization boundary around legacy Prometheus metrics;
- SQLite restart-survival coverage;
- adversarial and backward-compatibility coverage.

V2.6 does not redefine the canonical V1 rewrite workflow.

V2.6 does not redefine the frozen V2.3 Claim Lock contract.

V2.6 does not redefine the frozen V2.4 multi-candidate control contract.

V2.6 does not redefine the frozen V2.5 long-document control contract.

## Persistent observability domain contract

Persistent observability event version:

`observability-event-v1`

Workspace analytics version:

`workspace-analytics-v1`

Supported operation classifications are:

- `SINGLE_REWRITE`;
- `MULTI_CANDIDATE_REWRITE`;
- `LONG_DOCUMENT_REWRITE`.

Supported outcome classifications are:

- `SUCCEEDED`;
- `CONTROLLED_FAILURE`;
- `SYSTEM_FAILURE`.

Supported control-decision classifications are:

- `PASS`;
- `WARN`;
- `FAIL`;
- `VIOLATION`;
- `NOT_EVALUATED`.

Persistent observability events bind only structured operational evidence,
including:

- event identity;
- workspace identity;
- user identity;
- operation;
- outcome;
- occurrence timestamp;
- duration;
- input/output character counts;
- provider execution evidence;
- provider fallback evidence;
- token usage;
- V1 release decision where applicable;
- Claim Lock decision where applicable;
- candidate count where applicable;
- section count where applicable;
- rewrite-history linkage where applicable;
- candidate-set linkage where applicable;
- long-document audit linkage where applicable;
- bounded failure category/code where applicable.

Persistent observability events do not carry:

- raw source text;
- rewritten text;
- prompts;
- protected-term collections;
- arbitrary unbounded metadata.

Successful events cannot carry failure classification.

Failure events require bounded failure classification.

Event timestamps must be timezone-aware.

Operation-specific dimensions must match the recorded operation.

## Persistent repository contract

The persistent observability repository contract supports:

- event creation;
- event lookup by ID;
- workspace-scoped time-window listing.

Duplicate event IDs fail explicitly.

Workspace listing uses the half-open window:

`period_start <= occurred_at < period_end`

Workspace listing is deterministic and ordered by:

1. `occurred_at`;
2. `event_id`.

The repository applies the requested limit after deterministic ordering.

Query timestamps must be timezone-aware.

`period_end` must be later than `period_start`.

The query limit must be at least one.

SQLite observability storage uses an isolated observability-events table and
survives repository/service reconstruction.

The repository does not persist raw rewrite content in observability columns.

## Recording integrity

The recording service accepts only the bounded structured observability input
contract.

The recording sequence is:

1. construct the frozen persistent event;
2. validate the complete event;
3. call repository creation exactly once;
4. compare the returned persisted event with the supplied event;
5. fail closed when the returned object differs.

Persistence exceptions propagate.

The recording service does not silently retry persistence.

The recording service does not accept raw rewrite text, rewritten text,
prompts, protected-term collections, or arbitrary metadata.

Event timestamp authority belongs to the recording service clock.

## Single-rewrite instrumentation

Persistent single-rewrite observability is additive to the existing execution
chain.

The existing authority order remains:

1. workspace membership;
2. Claim Lock preparation/validation;
3. canonical V1 rewrite execution;
4. rewrite-history persistence;
5. persistent observability recording.

Completed single-rewrite telemetry is emitted only after successful
rewrite-history persistence.

The telemetry record links to the persisted rewrite-history ID.

Provider and token evidence are normalized from existing completed execution
evidence.

V2.6 does not rerun V1 verification or Claim Lock for observability.

Strict Claim Lock failures that prevent completion remain outside the completed
single-rewrite telemetry path in V2.6.

## Multi-candidate instrumentation

Persistent multi-candidate observability is additive to the frozen
multi-candidate execution path.

Observability occurs only after the existing rewrite-history and candidate
artifacts required for a completed operation have been produced.

The telemetry record may bind:

- rewrite-history ID;
- candidate-set ID;
- candidate count;
- normalized provider execution totals;
- normalized token totals;
- completed control decisions.

Observability does not rerun candidate generation, ranking, Claim Lock, V1
verification, or candidate controls.

## Long-document instrumentation

Persistent long-document observability is additive to the frozen V2.5
long-document path.

Observability occurs only after durable long-document audit persistence for a
completed operation.

The telemetry record may bind:

- long-document audit ID;
- section count;
- normalized provider execution totals;
- normalized token totals;
- completed V1/Claim Lock control evidence.

Observability does not rerun:

- structure detection;
- section planning;
- section rewrite orchestration;
- Claim Lock;
- cross-section consistency controls;
- reconstruction;
- long-document audit construction.

## Deterministic workspace analytics

Workspace analytics aggregation is pure and deterministic over an already
selected persistent event set.

Aggregation validates:

- workspace identity;
- timezone-aware period boundaries;
- half-open window membership for every event.

Source-event order cannot change the resulting snapshot.

All operation buckets are emitted in canonical operation order, including
zero-count buckets.

Aggregated totals include:

- event count;
- success count;
- controlled-failure count;
- system-failure count;
- duration;
- input characters;
- output characters;
- provider executions;
- fallback events;
- input tokens;
- output tokens;
- total tokens;
- per-operation outcome buckets.

The aggregator does not mutate source events.

`generated_at` is clock-controlled.

Analytics aggregation does not infer business outcomes beyond the persisted
observability evidence.

## Persistent analytics query service

Persistent analytics queries require canonical workspace membership before the
observability repository is read.

The query service is read-only.

The query service depends on the narrow event-reader capability required for
analytics.

The repository remains authoritative for persistent event selection and
half-open window filtering.

The deterministic aggregator remains authoritative for analytics totals.

Analytics queries use a bounded sentinel read:

`event_limit + 1`

Exactly `event_limit` events are permitted.

When the sentinel row proves that the requested window contains more events
than the configured analytics limit, the query fails closed and requires the
caller to narrow the requested time window.

The query service does not return silently truncated analytics.

## Workspace analytics API

Public endpoint:

`GET /api/v2/workspaces/{workspace_id}/analytics`

Required query parameters include:

- `user_id`;
- `period_start`;
- `period_end`.

The HTTP route delegates analytics authority to the persistent analytics query
service.

The route does not read the observability repository directly.

The route does not recompute analytics.

Expected boundary semantics include:

- malformed datetime syntax: `422 Unprocessable Entity`;
- invalid period ordering/window validation: `400 Bad Request`;
- workspace membership denial: `403 Forbidden`;
- analytics-window truncation: `409 Conflict`;
- successful complete analytics query: `200 OK`.

The response uses the frozen workspace analytics snapshot contract.

## Legacy metrics exposure boundary

The existing process-local Prometheus registry remains separate from the V2.6
persistent observability store.

V2.6 does not reinterpret the legacy metrics registry as durable analytics.

Public `/metrics` exposure is disabled unless this environment variable has a
nonblank value:

`HUMANIZE_METRICS_BEARER_TOKEN`

When metrics exposure is disabled:

`GET /metrics`

returns:

`404 Not Found`

When metrics exposure is enabled, the request must provide an exact:

`Authorization: Bearer <configured-token>`

match.

Missing, malformed, wrong-scheme, partial, prefix, suffix, and non-exact bearer
credentials are rejected.

Bearer-token comparison uses constant-time digest comparison.

Metrics authorization does not alter `/health` or `/ready` availability.

## Restart and adversarial hardening

V2.6-I verifies:

- SQLite observability survival after service reconstruction;
- persisted workspace membership remains authoritative after restart;
- unauthorized analytics access remains denied after restart;
- analytics query truncation fails closed;
- malformed analytics datetime syntax is rejected;
- analytics responses do not echo raw source rewrite text;
- analytics responses do not expose `source_text`;
- analytics responses do not expose `rewritten_text`;
- blank metrics-token configuration keeps metrics disabled;
- malformed authorization schemes are rejected;
- non-exact bearer tokens are rejected;
- health remains available when metrics are disabled;
- readiness remains available when metrics are disabled;
- V1 rewrite behavior remains available;
- V2 rewrite history remains available;
- completed V2 single rewrites still produce persistent observability.

V2.6-I required no production-code correction.

## Persistence support and known boundaries

V2.6 persistent observability supports:

- in-memory repositories;
- SQLite repositories.

The current V2 persistence configuration also defines an `external` backend,
but V2.6 does not claim an implemented external persistent-observability
repository.

V2.6 intentionally does not provide:

- raw-content analytics;
- prompt analytics;
- semantic interpretation of telemetry;
- model-generated analytics totals;
- unbounded analytics queries;
- silent analytics truncation;
- automatic retry of failed observability writes;
- completed telemetry for every pre-completion controlled failure;
- replacement of canonical V1 verification;
- replacement of Claim Lock;
- replacement of multi-candidate controls;
- replacement of long-document controls;
- durable replacement of the legacy process-local Prometheus registry;
- unauthenticated public Prometheus metrics when metrics exposure is enabled;
- public list/get endpoints for individual persistent observability events.

These boundaries define the V2.6 release contract and are not release defects.

## Frozen control surface

The following V2.6 behavior is frozen and requires explicit control review
before weakening or changing it:

- `observability-event-v1`;
- `workspace-analytics-v1`;
- structured content-minimized event fields;
- exclusion of raw source and rewritten text from the recording interface;
- timezone-aware event timestamps;
- operation-shape integrity;
- outcome/failure-classification integrity;
- exact token arithmetic;
- memory and SQLite observability persistence;
- duplicate event-ID rejection;
- deterministic workspace/time-window repository ordering;
- half-open analytics windows;
- validation before persistence mutation;
- exactly one recording-service repository create call;
- no silent persistence retry;
- fail-closed repository-return mismatch behavior;
- single-rewrite observability after successful history persistence;
- multi-candidate observability after completed persistent artifacts;
- long-document observability after durable audit persistence;
- no rerunning control logic for observability;
- deterministic analytics aggregation;
- canonical operation bucket order;
- source-order-independent snapshots;
- workspace authorization before analytics reads;
- narrow read-only analytics repository dependency;
- `event_limit + 1` truncation detection;
- complete-or-fail analytics query semantics;
- workspace-scoped analytics API;
- direct use of the frozen analytics snapshot response contract;
- `403` membership denial;
- `409` analytics truncation handling;
- `400` invalid analytics-window handling;
- `422` malformed datetime handling;
- metrics disabled by default when no bearer token is configured;
- exact bearer-token authorization when metrics are enabled;
- constant-time token comparison;
- no metrics-token effect on health/readiness;
- SQLite restart survivability;
- analytics raw-content non-disclosure;
- V1 backward compatibility;
- existing V2 history compatibility;
- no V2.3 Claim Lock behavior changes;
- no V2.4 multi-candidate behavior changes;
- no V2.5 long-document behavior changes.

## Required evidence after frozen-control changes

Any future change to the frozen V2.6 control surface must include, as
applicable:

1. updated observability-domain tests when event or analytics contracts change;
2. updated repository tests when persistence or query semantics change;
3. updated recording-service tests when write integrity changes;
4. updated single-rewrite instrumentation tests when its sequencing changes;
5. updated multi-candidate observability tests when its telemetry mapping changes;
6. updated long-document observability tests when its telemetry mapping changes;
7. updated analytics-aggregator tests when deterministic totals change;
8. updated analytics-query tests when authorization, limits, or read behavior change;
9. updated analytics API tests when HTTP request/response semantics change;
10. updated metrics exposure tests when authentication semantics change;
11. updated SQLite restart tests when persistence or composition changes;
12. updated adversarial tests;
13. updated V1 backward-compatibility tests;
14. updated V2 history/rewrite compatibility tests;
15. Ruff validation;
16. mypy validation;
17. passing bounded V2.6 observability regression;
18. passing V2.6 adversarial/restart regression;
19. passing backward-compatibility regression;
20. passing complete V2 test suite;
21. passing complete API/repository test suite;
22. `git diff --check` validation;
23. confirmation that protected V1 files were not unintentionally modified;
24. confirmation that frozen V2.3 Claim Lock behavior was not unintentionally modified;
25. confirmation that frozen V2.4 multi-candidate behavior was not unintentionally modified;
26. confirmation that frozen V2.5 long-document behavior was not unintentionally modified;
27. updated release documentation describing the frozen-control change.

## V2.6 release gate

The V2.6 release gate requires:

- Ruff clean;
- mypy clean;
- V2.6 A–I observability regression passing;
- V2.6 adversarial/restart suite passing;
- backward-compatibility regression passing;
- complete V2 suite passing;
- complete API/repository suite passing;
- `git diff --check` clean;
- no unintended frozen V2.6 A–I implementation changes;
- no unintended protected V1 workflow changes;
- no unintended V2.3 Claim Lock changes;
- no unintended V2.4 multi-candidate changes;
- no unintended V2.5 long-document changes;
- no unintended legacy metrics-core changes outside the frozen H exposure boundary;
- release documentation is the only V2.6-J working-tree change;
- release commit parent is the exact published V2.6-I SHA;
- release branch remote matches the exact release commit after publication.

## Release interpretation

V2.6 is a persistent observability and deterministic analytics release.

It establishes durable, content-minimized operational evidence for completed
V2 rewrite operations and a workspace-authorized analytics read path over that
evidence.

Persistent observability remains subordinate to the existing rewrite control
planes. It does not become an authority for factual verification, Claim Lock,
candidate selection, long-document structure, reconstruction, or release
decisions.

The LLM does not determine observability authorization, persistence integrity,
analytics totals, query truncation, or metrics access.

The V2.6 control surface is frozen at release and must not be weakened without
explicit control review and updated release evidence.
