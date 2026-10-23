# Humanize V3.8 / V3.9 - DOCX, PDF, PPTX Amendment Acceptance Matrix R1

## Status

Detached architecture-amendment acceptance candidate.

This matrix defines acceptance obligations for the additive V3.8/V3.9 amendment. Passing this matrix in a later authorized review does not itself grant renderer implementation or runtime authority.

## A. Historical immutability

| ID | Requirement |
|---|---|
| A01 | Historical V3 activation, roadmap, and acceptance documents retain exact accepted Git blob identities. |
| A02 | The five accepted base V3.8 architecture documents retain exact accepted Git blob identities. |
| A03 | The amendment is represented as additive overlay architecture rather than retroactive historical edits. |
| A04 | Historical NONPASS/PASS dispositions remain immutable evidence. |

## B. Phase-boundary correctness

| ID | Requirement |
|---|---|
| B01 | Effective V3.8 scope includes deterministic DOCX, PDF, and PPTX rendering primitives. |
| B02 | V3.8 PPTX input is an explicit approved `PresentationRenderPlan`. |
| B03 | V3.8 PPTX output is limited to exact internal bytes, hashes, descriptors, and render evidence. |
| B04 | V3.8 receives no executive-narrative authority. |
| B05 | V3.8 receives no audience-adaptation authority. |
| B06 | V3.8 receives no presentation-storyline authority. |
| B07 | V3.9 retains executive presentation composition and delivery semantics. |
| B08 | V3.9 may produce an approvable explicit `PresentationRenderPlan`. |
| B09 | V3.9 may not reinterpret exact renderer artifact identity. |
| B10 | V3.10 complete handoff-package boundary remains unchanged. |

## C. Shared render bindings

| ID | Requirement |
|---|---|
| C01 | PPTX preserves `RenderSourceBinding`. |
| C02 | PPTX assets are exact and hash-bound. |
| C03 | PPTX templates are exact and hash-bound. |
| C04 | PPTX render profiles bind renderer/toolchain identity. |
| C05 | Tenant and engagement bindings are exact. |
| C06 | Classification is preserved. |
| C07 | Required provenance remains bound. |
| C08 | V3.6 approval binds the exact presentation composition being rendered. |
| C09 | Ambient host state is excluded from semantic render input. |

## D. Presentation render-plan contract

| ID | Requirement |
|---|---|
| D01 | `PresentationRenderPlan` is semantically distinct from `DocumentRenderPlan`. |
| D02 | Slide ordering is explicit and identity-participating. |
| D03 | Layout/master/theme references are explicit. |
| D04 | Speaker notes are rendered only when explicitly approved in the plan. |
| D05 | Renderer may not synthesize, summarize, expand, or rewrite speaker-note meaning. |
| D06 | Material claims bind source/provenance references. |
| D07 | Chart inputs are explicit and governed. |
| D08 | Diagram inputs are exact assets or exact deterministic declarative specifications. |
| D09 | `artifact_kind` is exactly `PPTX` for a presentation render plan. |
| D10 | Plan identity excludes current time, random values, host paths, and mutable user state. |

## E. Common request/result contract

| ID | Requirement |
|---|---|
| E01 | `ArtifactRenderRequest` binds exact plan type, plan hash, artifact kind, renderer, renderer version, and profile hash. |
| E02 | A rendered PPTX result binds final exact artifact SHA-256. |
| E03 | Artifact identity changes when final bytes change. |
| E04 | Rendered state does not imply export authorized. |
| E05 | Rendered state does not imply client released. |
| E06 | V3.7 artifact descriptor conversion requires no semantic reinterpretation. |

## F. PPTX deterministic packaging

| ID | Requirement |
|---|---|
| F01 | ZIP entry ordering is deterministic. |
| F02 | ZIP timestamps and byte-affecting archive flags are deterministic. |
| F03 | Core, application, and custom properties are deterministic and minimized. |
| F04 | Slide identifiers are deterministic. |
| F05 | Relationship identifiers are deterministic. |
| F06 | Master, layout, and theme identities are deterministic. |
| F07 | Font behavior is pinned or deterministically qualified. |
| F08 | Media package paths and names are deterministic. |
| F09 | Notes-slide relationships are deterministic when notes are present. |
| F10 | Chart relationships and chart-data workbook bytes are deterministic when charts are present. |
| F11 | XML ordering that affects bytes is deterministic or normalized. |
| F12 | Current time cannot alter final bytes. |
| F13 | Random identifiers cannot alter final bytes. |
| F14 | Local temporary paths cannot alter final bytes. |
| F15 | Host identity cannot alter final bytes. |
| F16 | Locale defaults cannot alter final bytes unless explicitly profile-bound. |

## G. Active-content and external-reference security

| ID | Requirement |
|---|---|
| G01 | Macros are prohibited. |
| G02 | ActiveX is prohibited. |
| G03 | Executable OLE objects are prohibited. |
| G04 | Embedded executables are prohibited. |
| G05 | External template dependencies are prohibited. |
| G06 | Remote image/media fetching is prohibited in the renderer core. |
| G07 | External chart-data refresh is prohibited. |
| G08 | External relationships used as render inputs are prohibited. |
| G09 | Unapproved embedded files are prohibited. |
| G10 | Unsupported package parts fail closed. |

## H. Metadata and package safety

| ID | Requirement |
|---|---|
| H01 | Workstation names are not leaked. |
| H02 | Local file paths are not leaked. |
| H03 | Nondeterministic authoring timestamps are removed or normalized. |
| H04 | Unexpected comments/review metadata are rejected. |
| H05 | Path traversal fails closed. |
| H06 | Symbolic-link escape for local input acquisition fails closed. |
| H07 | Duplicate conflicting package parts fail closed. |
| H08 | Malformed relationships fail closed. |
| H09 | Unexpected content types fail closed. |

## I. Cross-format governance

| ID | Requirement |
|---|---|
| I01 | DOCX, PDF, and PPTX preserve protected facts. |
| I02 | DOCX, PDF, and PPTX preserve provenance obligations. |
| I03 | DOCX, PDF, and PPTX preserve classification obligations. |
| I04 | DOCX, PDF, and PPTX preserve exact approval binding. |
| I05 | Cross-format visual or structural identity is not required. |
| I06 | Cross-format semantic authority must not silently diverge. |

## J. V3.7 and release separation

| ID | Requirement |
|---|---|
| J01 | PPTX final bytes are hashed before artifact-specific V3.7 authorization. |
| J02 | A byte change invalidates prior artifact-specific authorization. |
| J03 | V3.7 remains manifest/export authority. |
| J04 | V3.8 cannot authorize client release. |
| J05 | V3.9 cannot infer release from successful rendering. |
| J06 | Local file existence does not constitute receipt evidence. |

## K. Failure semantics

| ID | Requirement |
|---|---|
| K01 | Input hash mismatch fails closed. |
| K02 | Missing/stale approval binding fails closed. |
| K03 | Tenant or engagement mismatch fails closed. |
| K04 | Missing required provenance fails closed. |
| K05 | Classification weakening fails closed. |
| K06 | Nondeterministic renderer behavior fails qualification. |
| K07 | Prohibited active content fails validation. |
| K08 | Prohibited external relationships fail validation. |
| K09 | Unsupported package behavior fails validation. |
| K10 | Post-render validation uncertainty fails closed. |

## L. Explicit non-authority

| ID | Requirement |
|---|---|
| L01 | Amendment acceptance grants no renderer implementation authority. |
| L02 | Amendment acceptance grants no PPTX runtime authority. |
| L03 | Amendment acceptance grants no dependency-installation authority. |
| L04 | Amendment acceptance grants no export authority. |
| L05 | Amendment acceptance grants no client-release authority. |
| L06 | Amendment acceptance grants no deployment authority. |
| L07 | Amendment acceptance grants no V3.9 implementation authority. |
| L08 | Amendment acceptance grants no V3.10 implementation authority. |

## Acceptance interpretation

Architecture acceptance requires every applicable matrix requirement to pass.

A future implementation phase must define executable positive and negative tests derived from this matrix rather than treating architecture acceptance as runtime qualification.
