# HUMANIZE V3.5 — Composition Authority and Provenance Matrix R1

Status: DETACHED PLANNING CANDIDATE — NOT CANONICAL — NO IMPLEMENTATION AUTHORITY

## 1. Matrix purpose

This matrix defines how V3.5 Governed Composition must preserve V3.4 authority while assembling multiple inputs. It is normative for the planning candidate but is not canonical until separately accepted and materialized through later gates.

| Input / condition | V3.5 may inspect | V3.5 may preserve | V3.5 may change | Required disposition |
|---|---|---|---|---|
| V3.4 `ELIGIBLE` protected fact | yes | all authority/provenance/classification bindings | none | eligible for authoritative composition |
| V3.4 `PRESENTATION_ONLY` derivation | yes | derivation and source bindings | cannot promote to protected fact | presentation-only lane |
| V3.4 `BLOCK` input | yes | block evidence | none | `BLOCK`; no authoritative output |
| V3.4 `ERROR` input | yes | error evidence | none | `ERROR`; no authoritative output |
| tenant mismatch | yes | evidence of mismatch | none | `BLOCK` |
| engagement mismatch | yes | evidence of mismatch | none | `BLOCK` |
| missing required provenance structure | yes | available evidence | cannot repair or invent provenance | `ERROR` |
| differing protected-fact classification values | yes | each original value | cannot infer hierarchy or downgrade | `BLOCK` |
| requested classification equals inherited value | yes | exact value | none | allowed |
| requested classification differs from inherited value | yes | original value | cannot downgrade/change | `BLOCK` |
| exact duplicate protected-fact identity and bindings | yes | each input reference | cannot invent new fact | deterministic duplicate evidence |
| conflicting protected-fact binding key | yes | every conflicting source | cannot choose winner | `BLOCK` |
| presentation derivation mixed with protected facts | yes | both lanes distinctly | cannot make presentation authoritative | `ELIGIBLE` only for protected-fact lane; presentation remains presentation |
| presentation-only inputs only | yes | derivation evidence | cannot invent protected fact | `PRESENTATION_ONLY` |
| source authority binding | yes | exact binding | cannot substitute or rewrite | preserve |
| Claim Lock evidence | yes | exact evidence/result | cannot revalidate or reinterpret as new truth | preserve |
| composition ordering position | yes | explicit position | may only sort by declared position | deterministic |
| composition hash | yes | internal identity | cannot use as truth/provenance authority | identity only |

## 2. Authority precedence

There is no truth-authority precedence algorithm in V3.5.

NEXUS truth authority remains external. V3.5 does not select among competing truth claims. If V3.4-authorized protected-fact inputs conflict under the protected-fact binding key, V3.5 blocks composition rather than choosing a winner.

Disposition precedence for malformed or prohibited input sets is deterministic:

1. structural/contract failure -> `ERROR`
2. explicit V3.4 `ERROR` -> `ERROR`
3. explicit V3.4 `BLOCK` -> `BLOCK`
4. cross-tenant or cross-engagement condition -> `BLOCK`
5. classification or protected-fact authority conflict -> `BLOCK`
6. presentation-only set -> `PRESENTATION_ONLY`
7. otherwise -> `ELIGIBLE`

The implementation architecture must define one exact precedence ordering and test it adversarially.

## 3. Provenance ledger requirements

For every composition input, the output evidence must preserve:

- input identifier
- input position
- source artifact reference
- source authority binding identity
- provenance binding identity
- classification
- content kind
- protected-fact or presentation-derivation identity
- applicable Claim Lock evidence reference
- originating V3.4 disposition

No input may disappear from the evidence ledger without an explicit fail-closed disposition.

## 4. Protected-fact lane

The protected-fact lane carries only already-authorized `ProtectedDeliveryFact` references.

V3.5 may group and order these references, but it may not:

- edit the fact value
- change the authority binding
- change provenance
- change classification
- infer a stronger claim
- combine multiple facts into a new protected fact
- resolve contradictory facts

Any semantic synthesis of multiple facts into new authoritative truth is outside V3.5 authority.

## 5. Presentation lane

The presentation lane carries `PresentationDerivation` references and retains `PRESENTATION_ONLY` semantics where applicable.

A presentation derivation may support layout or narrative composition later, but V3.5 cannot convert it into a protected delivery fact or use it to overwrite an authoritative fact.

## 6. Mixed composition

A mixed composition may contain both lanes in the same immutable envelope only if the lanes remain explicitly distinguishable.

The existence of protected facts does not elevate presentation derivations. The existence of presentation derivations does not weaken or alter protected facts.

## 7. Tenant and engagement isolation

Every composition request is bound to exactly one tenant and one engagement.

All inputs must match both identifiers exactly. No administrator flag, caller override, presentation purpose, or composition hash may bypass this rule.

Cross-tenant and cross-engagement composition fails closed.

## 8. Classification rule

V3.5 has no classification lattice.

Therefore:

- exact equality is the only implicit compatibility rule.
- unequal authoritative classifications are not merged.
- no "highest classification wins" rule may be invented without a separately canonical taxonomy and explicit authority.
- no downgrade is permitted.

## 9. Provenance non-rewrite examples

Disallowed:

- replacing several source references with a synthetic "composed source"
- hashing multiple provenance bindings and presenting the hash as provenance
- copying provenance from one input to another
- dropping source bindings because two facts look equivalent
- changing a source reference to make two inputs appear compatible

Allowed:

- aggregate ledger containing every original provenance binding
- deterministic internal hash over the aggregate metadata for identity only
