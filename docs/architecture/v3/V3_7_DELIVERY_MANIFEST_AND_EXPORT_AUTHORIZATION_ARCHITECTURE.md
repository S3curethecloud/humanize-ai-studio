# Humanize V3.7 - Delivery Manifest and Export Authorization Architecture R1

## Status

Detached architecture planning candidate only.

This document does not mutate the governed repository and does not grant implementation, validation, repository materialization, staging, commit, push, PR, merge, provider, export-runtime, client-release, V3.8, V3.9, or V3.10 authority.

## Canonical predecessor

The only accepted predecessor for this candidate is the terminally closed V3.6 Human Approval Lifecycle implementation:

- canonical commit: `671d65ebcb89d150167e8b6049cecaee5f17bd0f`
- canonical tree: `df898ce978b3bc96ac47447a5c484ec8d4fd8a55`
- V3.6 terminal closure remains closed and is not reopened by V3.7 planning.

V3.7 consumes accepted V3.6 approval evidence. It does not alter V3.6 approval semantics or mutate any V3.6 record.

## Purpose

V3.7 plans deterministic delivery-manifest construction and explicit export authorization for client-delivery artifacts while preserving tenant and engagement scope, source evidence identity, provenance, classification, V3.6 approval state, and the distinction between artifact generation, export authorization, and client release.

The phase exists to answer two different questions:

1. What exact artifacts and authoritative references make up this delivery package?
2. Is this exact artifact/package state authorized for the intended audience and delivery context?

Those questions must remain separate.

## Canonical V3.7 boundary

The canonical roadmap requires candidate manifest content for:

1. tenant;
2. engagement;
3. package identity;
4. artifact identities;
5. artifact hashes;
6. source bundle identity;
7. source bundle version;
8. provenance references;
9. classification;
10. approvals;
11. export decision;
12. generation metadata.

The export authorization decision must consider at least:

- tenant;
- engagement;
- artifact identity;
- artifact version;
- classification;
- approval state;
- manifest identity;
- intended audience;
- allowed delivery context.

## Required lifecycle separation

The governing lifecycle remains:

```text
evidence accepted
!=
content composed
!=
content approved
!=
artifact generated
!=
export authorized
!=
client released
```

V3.7 owns only the delivery-manifest and export-authorization portion of that lifecycle.

V3.7 does not create client-release authority.

## Reuse-first predecessor inventory

V3.7 planning must consume and preserve existing V3 semantics before proposing new types.

### `app.v3.ndeb`

Reuse responsibility:
- source bundle identity and version;
- validated bundle/evidence references;
- bundle provenance and integrity results already accepted by Humanize;
- no NEXUS mutation and no authoritative NDEB generation.

### `app.v3.composition`

Reuse responsibility:
- exact governed composition identity;
- exact composition hash;
- preserved tenant and engagement identity;
- preserved classification and provenance ledgers;
- preserved source disposition.

### `app.v3.approval`

Reuse responsibility:
- exact approval request identity;
- exact V3.6 approval state;
- exact approval trace hash;
- exact composition identity/hash binding;
- no approval reinterpretation or mutation.

### `app.v3.authority`

Reuse responsibility:
- existing authority/disposition semantics where compatible;
- no provider/IAM lookup in the provider-free V3.7 core;
- no widening of upstream authority.

## Two-stage manifest model

A final manifest cannot safely be used as an input to an export decision if that same manifest identity already includes the export decision. V3.7 therefore separates the immutable manifest subject from the final delivery manifest.

### Stage A - `DeliveryManifestSubject`

The manifest subject binds the exact package state before export authorization:

- tenant and engagement;
- package identity;
- artifact descriptors;
- source bundle identity/version;
- provenance references;
- classification;
- V3.6 approval binding;
- deterministic generation metadata.

`manifest_subject_hash` is computed from that canonical subject.

### Stage B - `ExportAuthorizationDecision`

The export evaluator consumes the exact `manifest_subject_hash` plus explicit audience, delivery context, and export-policy authority. It returns `AUTHORIZED`, `DENIED`, or `ERROR` and a deterministic decision trace.

### Stage C - `DeliveryManifest`

The final manifest is the exact manifest subject plus the exact export decision and decision identity. The final manifest identity is computed only after the decision exists.

This removes circular identity while preserving the roadmap requirement that the delivered manifest records the export decision.

## Inputs

V3.7 planning expects later implementation to consume only already-governed inputs:

- exact V3.3 accepted bundle identity/version or equivalent accepted NDEB consumption result;
- exact V3.5 governed composition identity/hash and preserved authority/provenance/classification surface;
- exact V3.6 approval result with `approval_state=APPROVED` for the same composition;
- exact generated artifact descriptors supplied by a separately authorized generator or test fixture;
- explicit export authorization policy binding;
- explicit intended audience;
- explicit allowed delivery context.

V3.7 does not itself render DOCX, PDF, or PPTX artifacts.

## Outputs

A later separately authorized V3.7 implementation may produce:

- deterministic manifest-subject identity;
- deterministic package identity;
- deterministic normalized artifact set;
- deterministic export-authorization request identity;
- explicit export decision;
- explicit failure codes;
- deterministic export-decision trace hash;
- final delivery-manifest identity and manifest hash.

## Core invariants

1. V3.6 terminal closure remains immutable history.
2. NEXUS remains authoritative for upstream architecture and approved source evidence.
3. Humanize V3.7 never creates or mutates authoritative NDEB truth.
4. V3.7 consumes exact accepted predecessor identities; it never silently rebinds them.
5. Manifest construction and export authorization are different operations and different authorities.
6. Artifact generation never implies export authorization.
7. Export authorization never implies client release.
8. Every manifest and export decision is tenant- and engagement-bound.
9. Every artifact is identified by explicit artifact identity, version, and content hash.
10. Artifact ordering is deterministic and duplicate/conflicting identities fail closed.
11. Source bundle identity/version and provenance are mandatory manifest bindings.
12. Classification may be preserved or strengthened by separately governed policy, but never silently weakened.
13. V3.6 approval must bind the same exact composition/package source surface used by V3.7.
14. Stale, missing, ambiguous, contradictory, or cross-tenant approval evidence fails closed.
15. Intended audience and allowed delivery context are explicit authorization inputs.
16. Unknown or ambiguous export-policy authority fails closed.
17. Core identity and decision semantics use no current-time read, randomness, network, provider call, database lookup, filesystem discovery, or mutable process state.
18. Generation metadata that participates in identity must be deterministic input, not ambient runtime metadata.
19. Final manifest identity cannot be computed until the export decision is fixed.
20. V3.7 success authorizes no V3.8 rendering, V3.9 executive-delivery, or V3.10 handoff-package behavior.

## Proposed provider-free namespace for later implementation planning

A later implementation review may consider a single bounded namespace such as:

`app.v3.delivery`

Candidate modules may include:

- `contracts.py`
- `identity.py`
- `ordering.py`
- `manifest.py`
- `authorization.py`
- `service.py`
- `__init__.py`

This detached planning candidate grants no repository path or source-file creation authority.

## Explicitly excluded

- artifact rendering;
- DOCX/PDF/PPTX generation;
- client release or transmission;
- email, upload, storage, provider, or network side effects;
- provider IAM lookup;
- database persistence;
- repository mutation;
- NEXUS mutation;
- NDEB schema definition or generation;
- V3.6 approval mutation;
- policy administration;
- destination connector implementation;
- deployment;
- production enforcement.

## Successor boundary

Only a separately accepted V3.7 implementation may realize these semantics.

Only a separately authorized V3.8 or later capability may render client delivery artifacts.

Only a separately reviewed release/delivery authority may actually transmit or release a client artifact.
