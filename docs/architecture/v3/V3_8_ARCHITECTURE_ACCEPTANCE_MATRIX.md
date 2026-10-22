# Humanize V3.8 - Architecture Acceptance Matrix R1

## Status

Architecture-level acceptance cases for the V3.8 DOCX and PDF Delivery candidate. No implementation authority is granted.

## Predecessor and authority cases

1. V3.7 terminal closure is rebound exactly -> candidate may be evaluated.
2. V3.7 terminal closure identity mismatch -> acceptance fails.
3. Any attempt to reopen V3.7 -> acceptance fails.
4. V3.6 approval is `APPROVED` and binds exact composition -> render eligibility may continue.
5. V3.6 approval is `PENDING` -> render request not eligible.
6. V3.6 approval is `REJECTED` -> render request not eligible.
7. V3.6 approval is `REVISION_REQUIRED` -> render request not eligible.
8. Approval request/composition hash mismatch -> `ERROR`.
9. Cross-tenant source/approval -> `ERROR`.
10. Cross-engagement source/approval -> `ERROR`.

## Render-plan identity cases

11. Same logical plan with same ordered blocks -> same render-plan hash.
12. Changed authoritative text -> different render-plan hash.
13. Changed classification -> different render-plan hash.
14. Changed provenance -> different render-plan hash.
15. Changed template hash -> different render-plan hash.
16. Changed asset hash -> different render-plan hash.
17. Changed render profile -> different render-plan hash.
18. Changed renderer version -> new qualified generation profile required.
19. Ambient host path change -> no semantic identity change.
20. Process PID change -> no semantic identity change.
21. Current wall clock change -> no semantic identity change.
22. Locale change outside explicit profile -> no semantic identity change or fail qualification if renderer cannot guarantee it.

## DOCX deterministic cases

23. Same exact plan/profile/toolchain -> byte-identical qualified DOCX.
24. ZIP entry ordering is deterministic.
25. ZIP entry timestamps are deterministic/normalized.
26. Core/custom document properties are deterministic.
27. Relationship identifiers are deterministic.
28. Style and numbering identifiers are deterministic.
29. Same exact embedded media -> same media parts/hashes.
30. Macro-bearing output -> `ERROR`.
31. OLE/executable embedded payload -> `ERROR`.
32. External template relationship -> `ERROR`.
33. Auto-fetch external resource relationship -> `ERROR`.

## PDF deterministic cases

34. Same exact plan/profile/toolchain -> byte-identical qualified PDF.
35. Page size/margins are profile-bound.
36. Font set is explicitly bound where layout depends on fonts.
37. Silent font substitution -> `ERROR` unless explicitly qualified by profile.
38. Creation/modification timestamps are deterministic/normalized.
39. PDF document IDs are deterministic/normalized where emitted.
40. Producer/creator metadata is deterministic/normalized where byte-affecting.
41. JavaScript -> `ERROR`.
42. Launch action -> `ERROR`.
43. Unapproved embedded file -> `ERROR`.
44. Hidden network dependency -> `ERROR`.

## Cross-format semantic cases

45. Same render plan -> DOCX/PDF preserve identical authoritative facts.
46. Same render plan -> DOCX/PDF preserve identical classification.
47. Same render plan -> DOCX/PDF preserve identical approval binding.
48. Same render plan -> DOCX/PDF preserve required provenance bindings.
49. Format-specific pagination difference explicitly allowed by profile -> valid.
50. Format-specific omission of authoritative section not declared by plan -> `ERROR`.
51. Format-specific wording change to protected fact -> `ERROR`.

## Artifact identity and V3.7 binding cases

52. Final artifact SHA-256 is computed after normalization/security validation.
53. Same final bytes -> same SHA-256.
54. Any byte change -> changed SHA-256.
55. Any byte change -> prior artifact-specific V3.7 authorization becomes stale.
56. V3.8 artifact descriptor converts directly to V3.7 required descriptor fields.
57. Artifact descriptor source composition differs from render plan -> `ERROR`.
58. Artifact descriptor hash differs from final bytes -> `ERROR`.
59. Successful render does not imply V3.7 `AUTHORIZED`.
60. V3.7 `AUTHORIZED` does not imply client release.
61. V3.8 never manufactures client-release evidence.

## Asset/template security cases

62. Asset hash mismatch -> `ERROR`.
63. Template hash mismatch -> `ERROR`.
64. Duplicate asset identity/version with conflicting hashes -> `ERROR`.
65. Path traversal -> `ERROR`.
66. Symbolic-link escape -> `ERROR`.
67. Missing required local resource -> `ERROR`.
68. Network URL used as unresolved render dependency -> `ERROR`.

## Failure and partial-output cases

69. Renderer crash -> `ERROR`; no successful artifact.
70. Normalizer failure -> `ERROR`; no successful artifact.
71. Security validator failure -> `ERROR`; no successful artifact.
72. Semantic parity validation failure -> `ERROR`.
73. Partial file exists after failure -> remains non-authoritative.
74. Unknown renderer/toolchain identity -> `ERROR`.
75. Unsupported artifact kind -> `ERROR`.
76. Ambiguous generation profile -> `ERROR`.

## Non-authority cases

77. Architecture acceptance -> no implementation authority.
78. Renderer implementation -> no client release authority.
79. Artifact generation -> no export authorization authority.
80. Artifact generation -> no V3.9 PPTX authority.
81. Artifact generation -> no V3.10 handoff-package authority.
82. V3.8 cannot mutate NEXUS truth.
83. V3.8 cannot mutate V3.5 composition.
84. V3.8 cannot mutate V3.6 approval evidence.
85. V3.8 cannot reinterpret V3.7 export decision.

## Architecture acceptance threshold

The V3.8 architecture candidate is acceptable only if all 85 cases are representable while preserving:

- V3.7 terminal closure;
- upstream truth authority;
- tenant and engagement isolation;
- exact source composition and approval binding;
- provenance and classification retention;
- one canonical semantic render plan;
- qualified deterministic DOCX/PDF bytes;
- exact final artifact hashing;
- V3.7 artifact-descriptor compatibility;
- artifact-generation/export-authorization/client-release separation;
- fail-closed active-content and resource handling;
- no network dependency in rendering core;
- no V3.9 or V3.10 authority.
