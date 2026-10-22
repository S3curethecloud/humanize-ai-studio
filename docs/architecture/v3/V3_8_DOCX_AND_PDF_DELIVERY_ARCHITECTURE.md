# Humanize V3.8 - DOCX and PDF Delivery Architecture R1

## Status

V3.8 architecture planning candidate for the new post-V3.7 milestone.

This document does not reopen V3.7. V3.7 architecture publication is terminally closed at commit `8767bda4b109475f0337f38be22f31b5076c38a7` with reopen authority `NONE`.

Publication of this candidate does not establish V3.8 architecture acceptance and grants no implementation, validation, rendering-runtime, export, client-release, deployment, provider, persistence, PR, merge, or successor-phase authority.

## Canonical predecessor

V3.8 begins only from the accepted V3.7 architecture-publication state:

- canonical commit: `8767bda4b109475f0337f38be22f31b5076c38a7`
- canonical tree: `01e8fda8d6aa16aa52128c584a49005a7a20787b`
- canonical parent: `671d65ebcb89d150167e8b6049cecaee5f17bd0f`
- V3.7 closure record SHA-256: `153feebf1b46cb17583d980e962eef448fcc6c39deeb5c8a680f7e54678faf48`
- V3.7 closure receipt SHA-256: `a3cc61193d88fb78aa93f60a4a100b93f80c206c3003842582f0bbc317770c4f`

V3.7 remains immutable history.

## Purpose

V3.8 plans governed DOCX and PDF artifact generation from already governed Humanize delivery state.

The phase must produce exact artifact bytes and exact artifact descriptors while preserving:

- tenant and engagement identity;
- source bundle identity and version;
- V3.5 governed composition identity and hash;
- V3.6 approval identity and trace;
- provenance references;
- classification;
- deterministic render-profile identity;
- final artifact byte hash;
- the V3.7 distinction between artifact generation, export authorization, and client release.

## Required lifecycle ordering

V3.8 resolves artifact generation without collapsing V3.7 authority boundaries:

```text
accepted evidence
-> governed composition
-> human approval
-> internal artifact render candidate
-> exact artifact byte hash / descriptor
-> V3.7 manifest subject
-> V3.7 export authorization
-> final delivery manifest
-> separately authorized client release
```

The exact artifact hash is not available until rendering finishes. Therefore V3.8 may create an internal render candidate after exact predecessor approval checks, but the generated artifact is not externally releasable until a later V3.7 authorization binds that exact artifact descriptor and returns `AUTHORIZED`.

V3.8 never treats generation as proof of export authorization or client receipt.

## Inputs

A later separately authorized implementation may consume only exact governed inputs:

- tenant and engagement identity;
- accepted source bundle identity/version;
- exact V3.5 composition identity/hash;
- exact V3.6 `APPROVED` binding for that composition;
- preserved provenance and classification;
- explicit artifact kind (`DOCX` or `PDF`);
- explicit document render plan;
- explicit template identity and hash, when a template is used;
- explicit render-profile identity and hash;
- explicit asset identities/hashes;
- explicit renderer/toolchain identity and version;
- explicit deterministic font-set identity/hash where PDF layout depends on fonts.

No ambient host state may silently become semantic input.

## Outputs

A later implementation may produce only internal governed render results such as:

- canonical document render-plan identity;
- deterministic artifact candidate identity;
- exact DOCX bytes and SHA-256;
- exact PDF bytes and SHA-256;
- exact artifact version;
- artifact descriptor compatible with V3.7;
- deterministic rendering trace/evidence;
- normalized render failure codes.

V3.8 output alone is not client-release evidence.

## Canonical render-plan model

Both DOCX and PDF generation must derive from one immutable `DocumentRenderPlan` rather than independently synthesizing content per format.

The render plan binds:

- tenant and engagement;
- source composition identity/hash;
- approval binding;
- source disposition;
- classification;
- normalized ordered sections and blocks;
- protected facts and provenance references;
- asset references and hashes;
- template identity/hash;
- render-profile identity/hash;
- document metadata that is allowed to affect bytes;
- format-independent layout semantics where feasible.

The same semantic render plan must not silently diverge between DOCX and PDF.

## Deterministic rendering boundary

Raw artifact bytes participate in V3.7 artifact hashes, so byte determinism is a security and authority requirement, not a cosmetic optimization.

A later implementation must pin and validate every byte-affecting input, including:

- renderer/toolchain version;
- templates;
- font set;
- image/asset bytes;
- locale;
- page size and margins;
- style definitions;
- numbering rules;
- metadata fields;
- archive-entry ordering and timestamps for DOCX;
- PDF metadata, document IDs, object ordering, and embedded-resource behavior.

Current time, random identifiers, host names, process IDs, temporary paths, network responses, and mutable user-profile state must not alter semantic output bytes.

If the selected toolchain cannot produce stable bytes under the supported execution environment, implementation must fail qualification rather than silently redefine artifact identity.

## DOCX requirements

A governed DOCX renderer must plan for:

- deterministic OPC package entry ordering;
- deterministic ZIP metadata/timestamps;
- deterministic core/custom properties;
- deterministic relationship identifiers;
- deterministic style and numbering identities;
- no macros;
- no executable embedded objects;
- no external template dependency;
- no unresolved external relationship that can fetch network content;
- explicit image/media hashes;
- preserved classification markings where required;
- deterministic document properties that participate in bytes.

## PDF requirements

A governed PDF renderer must plan for:

- pinned renderer and conversion chain;
- pinned fonts or explicitly qualified font substitution behavior;
- deterministic page geometry;
- deterministic metadata;
- deterministic document IDs where the format/toolchain emits them;
- no JavaScript;
- no launch actions;
- no hidden network dependency;
- no unapproved embedded files;
- no silent loss of classification markings;
- stable asset embedding;
- exact byte hashing after final normalization.

## Cross-format consistency

When DOCX and PDF are generated from the same render plan, qualification must prove that both preserve the same authoritative claims, provenance bindings, classification, approval binding, and intended document structure.

Visual pagination may differ by format only where explicitly allowed by the render profile. Semantic facts may not differ.

## V3.7 integration contract

V3.8 produces artifact descriptors for later V3.7 evaluation.

A V3.8 artifact descriptor must include at least:

- artifact identity;
- artifact version;
- artifact kind;
- artifact SHA-256;
- source composition identity/hash;
- generation profile identity/hash.

V3.7 remains the authority for delivery-manifest construction and export authorization.

V3.8 may consume an accepted V3.7 `AUTHORIZED` result only to mark an exact artifact as export-authorized for downstream release handling. V3.8 may not create or reinterpret that authorization.

## Security invariants

1. V3.7 terminal closure is immutable and not reopened.
2. NEXUS remains authoritative for upstream engagement truth.
3. Rendering may present authoritative truth but may not manufacture new authoritative facts.
4. Protected facts cannot be changed by formatting, pagination, templating, summarization, conversion, or metadata generation.
5. Tenant and engagement identity must remain exact through every render operation.
6. Classification must never be silently weakened or omitted.
7. Required provenance must remain bound to rendered content/evidence.
8. V3.6 approval must bind the exact composition being rendered.
9. Artifact identity is bound to exact final bytes.
10. Any byte change produces a different artifact hash and invalidates prior artifact-specific V3.7 authorization.
11. V3.8 must not transmit artifacts to a client.
12. V3.8 must not infer client release from download availability or local file existence.
13. Rendering core must not require network access.
14. External resources must be materialized and hash-bound before rendering.
15. Path traversal, symbolic-link escape, external relationship fetches, active content, and unsafe embedded payloads fail closed.
16. Unsupported or nondeterministic renderer behavior fails closed.

## Proposed namespace for later implementation planning

A later separately authorized implementation review may consider a bounded namespace such as:

`app.v3.rendering`

Candidate modules may include:

- `contracts.py`
- `identity.py`
- `render_plan.py`
- `assets.py`
- `docx.py`
- `pdf.py`
- `normalization.py`
- `validation.py`
- `service.py`
- `__init__.py`

No source path is authorized by this architecture candidate.

## Explicitly excluded

- client transmission or release;
- email or messaging delivery;
- public download publication;
- destination connectors;
- provider upload;
- storage ACL mutation;
- NEXUS mutation;
- authoritative NDEB generation;
- V3.5 composition mutation;
- V3.6 approval mutation;
- V3.7 authorization mutation or reinterpretation;
- PPTX generation;
- complete handoff packaging;
- production deployment;
- persistent render-job orchestration;
- background delivery jobs.

## Successor boundary

Only a separately accepted V3.8 architecture may proceed to implementation planning.

Only separately authorized V3.8 implementation may materialize renderer source code or execute governed rendering tests.

V3.9 remains responsible for PPTX and executive delivery.

V3.10 remains responsible for complete client handoff-package assembly.
