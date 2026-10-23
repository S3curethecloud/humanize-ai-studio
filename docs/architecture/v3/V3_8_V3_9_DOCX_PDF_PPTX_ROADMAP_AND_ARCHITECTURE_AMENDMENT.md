# Humanize V3.8 / V3.9 - DOCX, PDF, and PPTX Roadmap and Architecture Amendment R1

## Status

Detached architecture-amendment candidate.

This document is an additive overlay. It does not rewrite, supersede, or mutate the historical bytes of the accepted V3 client-delivery roadmap or the accepted V3.8 DOCX/PDF architecture package.

This candidate grants no implementation, validation, render-runtime, export, client-release, deployment, dependency-installation, PR, merge, or publication authority.

## Canonical predecessor and lineage

The candidate is prepared only from the canonical V3.8 state:

```text
CANONICAL_BASE_COMMIT=d51bb409c127fb91f3f2aa648ac87aa7fb79f37d
CANONICAL_BASE_TREE=0e7c63aa4b80e1d43e2834033545b8849d0ba77a
CANONICAL_BASE_PARENT=32d2b4acef1ed2dcec9c792b086f9261474f2a86
CANONICAL_SOT_SHA256=ed57d5e37701a5fe77f54436e9e6606cbf399a296d7852a16ff731e613503859
```

The amendment scope was qualified by:

```text
ROADMAP_ARCHITECTURE_AMENDMENT_SCOPE_SURFACE_SHA256=c725620d5d83eaae8089c3e9dc2564d21497ee9b2c98b6a09041aed50352ee97
AMENDED_PHASE_BOUNDARY_SHA256=e32190e08cbfd85206120c4ea02e1c5e81fec62fcd34181f8e9be5d9ea709968
```

Historical V3.0 and V3.8 architecture artifacts remain immutable evidence.

## Amendment model

```text
AMENDMENT_MODEL=ADDITIVE_OVERLAY_PRESERVING_ACCEPTED_HISTORICAL_BYTES
```

The effective phase boundary proposed by this amendment is:

```text
V3.8 = DOCX / PDF / PPTX deterministic rendering foundation
V3.9 = executive presentation composition and delivery
```

The amendment separates presentation intelligence from byte rendering.

## V3.8 effective responsibility

V3.8 gains a deterministic PPTX rendering primitive alongside the already accepted DOCX and PDF rendering responsibilities.

V3.8 may receive an exact approved `PresentationRenderPlan` and produce only an internal governed render result containing:

- exact PPTX bytes;
- exact artifact SHA-256;
- exact artifact size;
- exact artifact identity and version;
- render-plan identity;
- generation-profile identity;
- deterministic render evidence;
- normalized validation/failure evidence;
- an artifact descriptor compatible with the V3.7 export-authorization boundary.

V3.8 does not acquire authority to invent or materially rewrite presentation content.

V3.8 explicitly has no authority to decide:

- executive narrative;
- storyline;
- audience adaptation;
- speaker-note meaning;
- slide selection based on ambient context;
- architecture conclusions;
- protected facts;
- classification;
- provenance;
- approval state;
- export authorization;
- client release.

If speaker notes or other presentation content appear in the approved `PresentationRenderPlan`, V3.8 may render those exact approved inputs. It may not synthesize them.

## V3.9 effective responsibility

V3.9 remains the executive-presentation intelligence and delivery phase.

V3.9 may plan, subject to its own separate future authority:

- executive narrative;
- audience-aware presentation composition;
- slide storyline and ordering;
- speaker notes;
- presentation design intent;
- evidence-backed architecture diagrams and visual selections;
- presentation-specific composition decisions;
- an explicit approvable `PresentationRenderPlan`;
- presentation-package delivery semantics.

V3.9 may not reinterpret the exact artifact identity emitted by the V3.8 deterministic renderer.

## V3.8 / V3.9 handoff

The proposed phase handoff is:

```text
governed evidence
-> approved presentation composition
-> exact PresentationRenderPlan
-> human approval binding
-> V3.8 deterministic PPTX render
-> exact PPTX artifact descriptor
-> V3.7 export authorization
-> presentation package / release handling
```

The renderer is downstream of presentation-composition decisions.

## Shared rendering foundation

The amendment preserves the accepted V3.8 shared bindings:

- `RenderSourceBinding`;
- `RenderAsset`;
- `RenderTemplateBinding`;
- `RenderProfile`;
- exact tenant and engagement binding;
- provenance retention;
- classification retention;
- exact approval binding;
- deterministic asset and template hashes;
- explicit renderer/toolchain identity;
- exact final artifact byte hashing.

DOCX/PDF continue to use `DocumentRenderPlan`.

PPTX uses `PresentationRenderPlan`.

A common `ArtifactRenderRequest` envelope may bind either plan type to an explicit output format.

The effective artifact-kind set becomes:

```text
DOCX
PDF
PPTX
```

## V3.7 integration remains unchanged

V3.7 remains the authority for delivery-manifest construction and export authorization.

Rendering an artifact does not authorize its export.

Any byte change to DOCX, PDF, or PPTX produces a new artifact hash and invalidates any prior artifact-specific authorization.

## V3.10 boundary remains unchanged

V3.10 remains responsible for complete client handoff-package assembly.

Moving deterministic PPTX rendering into V3.8 does not move complete handoff-package responsibility into V3.8 or V3.9.

## Historical roadmap treatment

The historical documents remain unchanged:

- `V3_CLIENT_DELIVERY_ACTIVATION.md`;
- `V3_CLIENT_DELIVERY_PHASE_PLAN.md`;
- `V3_CLIENT_DELIVERY_ACCEPTANCE_CRITERIA.md`;
- all five accepted base V3.8 architecture documents.

The amendment is interpreted as a current-state overlay recorded by additive architecture documents and the current Canonical Source of Truth.

## Explicit non-authority

This candidate grants no authority for:

- renderer implementation;
- PPTX generation runtime;
- DOCX/PDF generation runtime;
- package installation;
- `python-pptx`, PptxGenJS, LibreOffice, Office automation, or other rendering-tool invocation;
- UI implementation;
- persistence changes;
- export authorization;
- client release;
- network renderers;
- deployment;
- mutation of historical roadmap documents;
- mutation of accepted V3.8 base architecture documents.

## Candidate acceptance boundary

The amendment becomes effective architecture only after its exact detached candidate is independently accepted and later published through separately authorized repository gates.

Until then:

```text
V3_8_IMPLEMENTATION_AUTHORITY=NONE
V3_8_RENDER_RUNTIME_AUTHORITY=NONE
PPTX_IMPLEMENTATION_AUTHORITY=NONE
PPTX_RENDER_RUNTIME_AUTHORITY=NONE
V3_9_IMPLEMENTATION_AUTHORITY=NONE
V3_9_RENDER_RUNTIME_AUTHORITY=NONE
```
