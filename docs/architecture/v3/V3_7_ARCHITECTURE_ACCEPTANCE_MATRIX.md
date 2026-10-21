# Humanize V3.7 - Architecture Acceptance Matrix R1

## Status

Detached architecture planning candidate only. These are architecture-level acceptance cases for a later separately authorized implementation and validation sequence.

## Positive manifest cases

1. Exact tenant/engagement, one artifact, valid source bundle, exact provenance/classification, V3.6 `APPROVED`, deterministic generation metadata -> stable manifest-subject hash.
2. Same logical artifact set in different input order -> identical normalized artifact ordering and manifest-subject hash.
3. Identical duplicate artifact descriptor -> idempotent normalized subject.
4. Multiple unique artifact descriptors -> canonical ordering by artifact identity/version/hash.
5. Same exact manifest subject -> same package identity and manifest-subject hash.
6. Same exact final subject plus same export decision -> same final delivery-manifest identity.

## Positive authorization cases

7. Exact approved subject + permitted classification + permitted audience + permitted delivery context + exact policy -> `AUTHORIZED`.
8. Exact `PRESENTATION_ONLY` source + V3.6 `APPROVED` + policy explicitly permits presentation-only delivery for exact context -> `AUTHORIZED` while source disposition remains `PRESENTATION_ONLY`.
9. Exact inputs with permuted allowed-set order -> same policy-normalized authorization result.
10. Exact authorization input repeated -> same request id, decision, decision id, and trace hash.

## Valid denial cases

11. Structurally valid subject but V3.6 state `PENDING` -> `DENIED`.
12. Structurally valid subject but classification not policy-permitted -> `DENIED`.
13. Structurally valid subject but audience not policy-permitted -> `DENIED`.
14. Structurally valid subject but delivery context not policy-permitted -> `DENIED`.
15. Structurally valid subject but source disposition not policy-permitted -> `DENIED`.

## Fail-closed identity and integrity cases

16. Cross-tenant subject/request -> `ERROR`.
17. Cross-engagement subject/request -> `ERROR`.
18. Artifact bytes/hash mismatch -> `ERROR`.
19. Artifact version mismatch -> `ERROR`.
20. Same artifact identity/version with conflicting hashes -> `ERROR`.
21. Manifest-subject hash mismatch -> `ERROR`.
22. Source bundle identity mismatch -> `ERROR`.
23. Source bundle version mismatch -> `ERROR`.
24. Missing required provenance -> `ERROR`.
25. Conflicting provenance binding -> `ERROR`.
26. Missing classification -> `ERROR`.
27. Classification binding inconsistent with preserved source -> `ERROR`.
28. Malformed artifact SHA-256 -> `ERROR`.
29. Malformed policy SHA-256 -> `ERROR`.
30. Malformed approval trace hash -> `ERROR`.

## V3.6 approval binding cases

31. V3.6 approval request binds different composition -> `ERROR`.
32. V3.6 approval trace binds different composition hash -> `ERROR`.
33. V3.6 `REJECTED` -> never `AUTHORIZED`.
34. V3.6 `REVISION_REQUIRED` -> never `AUTHORIZED`.
35. V3.6 `ERROR` -> never `AUTHORIZED`.
36. V3.6 `APPROVED` does not by itself imply `AUTHORIZED`.
37. V3.6 approval of `PRESENTATION_ONLY` never upgrades source disposition.

## Policy and context binding cases

38. Export policy hash mismatch -> `ERROR`.
39. Changed intended audience -> new export request identity required.
40. Changed delivery context -> new export request identity required.
41. Changed policy identity/hash -> new export request identity required.
42. Changed artifact set -> new manifest subject and new export request required.
43. Changed classification -> new manifest subject and new export request required.
44. Changed provenance -> new manifest subject and new export request required.

## Separation-of-authority cases

45. Artifact generation alone -> no export authorization.
46. Manifest-subject construction alone -> no export authorization.
47. Final delivery manifest with `DENIED` -> no export authorization.
48. Final delivery manifest with `ERROR` -> no export authorization.
49. `AUTHORIZED` export decision -> no client-release evidence.
50. Client release cannot be inferred from artifact existence, manifest existence, or export authorization.
51. V3.7 cannot render DOCX/PDF/PPTX.
52. V3.7 cannot mutate NEXUS or generate authoritative NDEB truth.
53. V3.7 cannot alter V3.5 composition bytes/provenance/classification.
54. V3.7 cannot alter V3.6 approval records or states.

## Determinism cases

55. Same logical inputs -> same package id.
56. Same logical inputs -> same manifest-subject hash.
57. Same logical export request -> same export request id.
58. Same logical decision inputs -> same decision and export trace hash.
59. Host clock change -> no core semantic change.
60. Locale change -> no core semantic change.
61. filesystem state change -> no core semantic change.
62. provider/network availability change -> no core semantic change.
63. input ordering change -> no semantic change after canonical normalization.
64. process PID/host/temp-path change -> no core identity change.

## Architecture acceptance threshold

The V3.7 architecture candidate is acceptable only if all 64 cases are representable while preserving:

- V3.6 terminal closure;
- NEXUS upstream truth authority;
- tenant and engagement isolation;
- exact artifact identity/version/hash binding;
- source bundle identity/version;
- provenance;
- classification;
- exact V3.6 approval binding;
- manifest/export-authority separation;
- export/client-release separation;
- deterministic canonical identity;
- fail-closed error semantics;
- provider-free core semantics;
- no repository, provider, network, render, export, or client-release side effects during architecture planning.
