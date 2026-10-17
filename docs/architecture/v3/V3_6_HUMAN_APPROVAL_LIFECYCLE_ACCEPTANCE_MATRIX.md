# Humanize V3.6 — Architecture Acceptance Matrix R1

## Positive cases

1. Valid `ELIGIBLE` composition + one required authorized approver + threshold 1 + `APPROVE` -> `APPROVED`.
2. Valid `ELIGIBLE` composition + threshold 2 + one approval -> `PENDING`.
3. Valid `ELIGIBLE` composition + threshold 2 + two required authorized approvals -> `APPROVED`.
4. Valid `PRESENTATION_ONLY` composition + valid approval -> `APPROVED` with source disposition still `PRESENTATION_ONLY`.
5. Identical duplicate approval decision -> idempotent normalized result.
6. Permuted input decision order -> byte-identical normalized result and trace hash.

## Terminal negative cases

7. Authorized `REJECT` -> `REJECTED`.
8. Authorized `REQUIRE_REVISION` -> `REVISION_REQUIRED`.
9. Revision creates a new upstream composition -> old request does not transfer.

## Fail-closed cases

10. V3.5 source `BLOCK` -> `ERROR`.
11. V3.5 source `ERROR` -> `ERROR`.
12. cross-tenant decision -> `ERROR`.
13. cross-engagement decision -> `ERROR`.
14. changed composition hash with old request -> `ERROR`.
15. changed approval policy hash with old request -> `ERROR`.
16. unknown approver -> `ERROR`.
17. unauthorized requested scope -> `ERROR`.
18. unauthorized decision type -> `ERROR`.
19. conflicting decisions from same approver -> `ERROR`.
20. malformed request hash -> `ERROR`.
21. duplicate approver identifiers in policy -> `ERROR`.
22. threshold zero -> `ERROR`.
23. threshold greater than required approver count -> `ERROR`.

## Non-authority cases

24. no decisions -> `PENDING`.
25. insufficient approvals -> `PENDING`.
26. approval of `PRESENTATION_ONLY` must not create authoritative protected fact.
27. `APPROVED` must not itself create delivery/export/render authority.
28. approval must not modify V3.5 composition bytes, provenance, classification, or authority trace.

## Determinism cases

29. same inputs -> same request id.
30. same authority binding -> same authority hash.
31. same decision -> same decision id.
32. equivalent decision set ordering -> same aggregate state and trace hash.
33. host time change -> no semantic change.
34. locale change -> no semantic change.
35. filesystem state change -> no semantic change.
36. provider/network availability change -> no semantic change in core evaluation.

## Architecture acceptance threshold

The candidate architecture is acceptable only if all 36 cases are representable without:
- network calls;
- provider calls;
- mutable clock reads;
- randomness;
- persistence;
- V3.5 content mutation;
- delivery/export authority;
- silent conflict resolution.
