# Humanize V3.4 Authority Preservation and Classification Matrix

## Status

```text
V3_4_MATRIX_STATUS=NONCANONICAL_CANDIDATE
V3_4_IMPLEMENTATION_AUTHORITY=NONE
```

This matrix freezes candidate V3.4 architecture decisions.

It is not an executable policy table and does not authorize runtime behavior.

## Decision vocabulary

The matrix uses architecture-level outcomes:

- `ELIGIBLE` - the condition is compatible with later downstream processing if
  all other required controls pass;
- `BLOCK` - downstream use must not proceed while the stated condition exists;
- `ERROR` - required authority cannot be established or the governance
  evaluation itself cannot be completed;
- `PRESENTATION_ONLY` - content may exist only as non-authoritative
  presentation state and must not be promoted to evidence.

Exact runtime enums and API mappings are deferred.

## Core matrix

| Condition | Required architecture outcome | Authority rule |
| --- | --- | --- |
| Source evidence reference resolves and required provenance is intact | `ELIGIBLE` | Source authority remains established |
| Required source reference is missing | `ERROR` | Material downstream authority cannot be established |
| Provenance reference is dangling or ambiguous | `ERROR` | Fail closed on unresolvable authority |
| Protected Delivery Fact exactly represents approved source material | `ELIGIBLE` | Downstream protection does not create new truth |
| Protected Delivery Fact changes the source fact | `BLOCK` | Humanize may not rewrite authoritative truth |
| Assumption is presented as an assumption | `ELIGIBLE` | Authority status is preserved |
| Assumption is converted into a confirmed fact without new source authority | `BLOCK` | Assumption-to-fact conversion is prohibited |
| Evaluation result remains failed, partial, inconclusive, or not-evaluated as sourced | `ELIGIBLE` | Evaluation authority is preserved |
| Evaluation failure is rewritten as success | `BLOCK` | Evaluation outcomes may not be inflated |
| Architecture decision is summarized without changing its meaning | `ELIGIBLE` | Presentation may adapt wording |
| Architecture decision is silently replaced or materially altered | `BLOCK` | Decision authority remains upstream |
| Source classification is preserved | `ELIGIBLE` | Classification floor is retained |
| Downstream handling is stricter than source handling | `ELIGIBLE` | Humanize may strengthen handling |
| Downstream handling weakens source classification without separately reviewed authority | `BLOCK` | Silent downgrade is prohibited |
| Classification semantics are required but authoritative taxonomy/order is unavailable | `ERROR` | Humanize must not invent classification ordering |
| Deterministically protected Claim Lock term/value is preserved | `ELIGIBLE` | Existing preservation control is satisfied |
| Deterministically protected Claim Lock term/value is violated under strict enforcement | `BLOCK` | Existing strict fail-closed semantics remain authoritative |
| Claim Lock audit-only violation exists | `ELIGIBLE` only as later policy permits with violation evidence retained | Audit evidence must not be erased |
| Semantic protected claim is exact-string absent but may be legitimate paraphrase | `ERROR` for semantic-equivalence determination by Claim Lock alone | Existing Claim Lock does not prove semantic equivalence |
| Material generated narrative is traceable to authoritative input | `PRESENTATION_ONLY` unless separately represented as protected authoritative state | Presentation is not evidence authority |
| Generated narrative lacks source support but is clearly presentation-only and non-material | `PRESENTATION_ONLY` | Presentation-only content must remain distinguishable |
| Generated narrative invents material project truth | `BLOCK` | Humanize may not manufacture truth |
| Tenant matches authorized delivery workspace | `ELIGIBLE` | Tenant isolation preserved |
| Source or protected fact belongs to a different tenant | `BLOCK` | Cross-tenant mixing prohibited |
| Engagement context matches applicable source authority | `ELIGIBLE` | Engagement isolation preserved |
| Engagement-specific source is reused in another engagement without reviewed reusable-artifact authority | `BLOCK` | Cross-engagement implicit reuse prohibited |
| Source approval meaning is preserved | `ELIGIBLE` | Approval authority is not rewritten |
| Humanize approval is represented as upstream source approval | `BLOCK` | Approval domains remain distinct |
| Source identifier is retained through resolvable reference | `ELIGIBLE` | Traceability remains intact |
| Source identifier is replaced by untraceable narrative | `BLOCK` | Provenance severance prohibited |
| Transformation changes style, organization, or audience level while preserving authority envelope | `ELIGIBLE` | Authority-preserving presentation change |
| Transformation removes a material caveat or unresolved state | `BLOCK` | Material uncertainty is authority-bearing |
| V3.4 state attempts to mutate NEXUS | `BLOCK` | Humanize remains downstream and read-only |
| V3.4 state attempts to authorize V3.5 composition runtime | `BLOCK` | Phase boundary must be preserved |

## Classification propagation matrix

This package does not define a classification taxonomy.

The following matrix therefore uses relative handling semantics only.

| Source handling | Proposed downstream handling | Candidate result |
| --- | --- | --- |
| authoritative source classification | same authoritative handling | `ELIGIBLE` |
| authoritative source classification | demonstrably stricter handling under later bound policy | `ELIGIBLE` |
| authoritative source classification | weaker handling | `BLOCK` |
| unknown source classification where classification is required | any claimed downstream classification | `ERROR` |
| conflicting required classification authorities | unresolved | `ERROR` |

No label ordering may be inferred from label spelling.

## Claim protection matrix

| Protected material | Candidate V3.4 requirement |
| --- | --- |
| Terminology | Preserve according to the existing Claim Lock matching semantics when that control is later integrated |
| Literal numbers, percentages, dates, URLs, identifiers, codes | Preserve exact deterministic values when protected by the existing Claim Lock contract |
| Semantic protected claims | Do not claim deterministic semantic equivalence from exact-string checks alone |
| Architecture decisions | Preserve decision meaning and source reference |
| Evaluation outcomes | Preserve outcome and failure/uncertainty state |
| Assumptions | Preserve assumption status unless new authoritative evidence establishes a fact |
| Approval state | Preserve source approval meaning; keep Humanize approval separate |
| Classification | Preserve source floor; never silently weaken |
| Provenance | Preserve resolvable source lineage |

## Cross-tenant negative matrix

| Attempt | Required result |
| --- | --- |
| Attach tenant A source reference to tenant B protected fact | `BLOCK` |
| Attach tenant A protected fact to tenant B delivery workspace | `BLOCK` |
| Use tenant A Claim Lock policy as authority for tenant B | `BLOCK` |
| Reuse tenant A classification context for tenant B without explicit reusable-artifact authority | `BLOCK` |
| Infer cross-tenant reuse from matching text or identifiers | `BLOCK` |

## V3.3 boundary matrix

| Behavior | V3.3 | V3.4 |
| --- | --- | --- |
| Validate inbound classification | Owns validation/preservation | Must not reinterpret validation |
| Validate inbound provenance | Owns validation/preservation | Builds downstream provenance architecture |
| Reject unsupported NDEB | Owns | Does not reopen |
| Protected Delivery Fact behavior | Does not own runtime | Candidate V3.4 architecture scope |
| Claim Protection after ingestion | Does not own runtime | Candidate V3.4 architecture scope |
| Classification propagation downstream | Does not own | Candidate V3.4 architecture scope |
| Authority-preserving transformation | Does not own | Candidate V3.4 architecture scope |

## V3.5 boundary matrix

| Behavior | V3.4 | V3.5 |
| --- | --- | --- |
| Preserve authority envelope | Owns candidate architecture | Consumes later if authorized |
| Protect authoritative facts | Owns candidate architecture | Must respect |
| Propagate classification | Owns candidate architecture | Must respect |
| Compose audience-facing narrative | Does not authorize | Successor responsibility |
| Template-driven composition | Does not authorize | Successor responsibility |
| Evidence-backed claim rendering | Provides protected inputs only | Successor responsibility |

## Final matrix invariant

If a downstream transformation cannot prove that required source authority,
provenance, tenant boundary, and classification are preserved, it is not
eligible to proceed as authoritative delivery state.
