# Humanize V3.8 / V3.9 - PPTX Rendering Boundary and Contracts R1

## Status

Detached architecture-amendment candidate only.

Contract names in this document are semantic architecture names. They are not authorized runtime classes or implementation types.

## Responsibility boundary

V3.9 may produce an approved presentation composition and an explicit `PresentationRenderPlan`.

V3.8 may deterministically render that exact approved plan into PPTX bytes.

The rendering boundary is intentionally narrow:

```text
presentation intelligence != artifact renderer
```

V3.8 may preserve approved meaning. It may not create new presentation meaning.

## Reused shared bindings

PPTX rendering reuses the existing V3.8 concepts:

### `RenderSourceBinding`

Binds:

- tenant;
- engagement;
- source bundle;
- governed composition;
- approval request and trace;
- classification;
- provenance;
- source disposition.

### `RenderAsset`

Binds exact asset identity, version, media type, and SHA-256.

Every image, diagram, media object, and chart-data payload that can affect PPTX bytes must be materialized and hash-bound before rendering.

### `RenderTemplateBinding`

For PPTX, a template binding may include:

- template identity;
- template version;
- template SHA-256;
- template kind;
- slide-master identity set;
- slide-layout identity set;
- theme identity;
- theme SHA-256.

External templates are prohibited.

### `RenderProfile`

For PPTX, the profile may additionally bind:

- renderer identity and version;
- normalizer identity and version;
- presentation aspect ratio;
- slide-size policy;
- theme policy;
- font-set identity and hash;
- relationship-ID policy;
- slide-ID policy;
- package-timestamp policy;
- metadata policy;
- notes policy;
- chart policy;
- media-embedding policy.

Ambient host state must not become an implicit profile input.

## `PresentationBlock`

Candidate semantic block kinds may include:

- `TITLE`;
- `SUBTITLE`;
- `BODY_TEXT`;
- `BULLET_LIST`;
- `NUMBERED_LIST`;
- `TABLE`;
- `IMAGE`;
- `DIAGRAM`;
- `CHART`;
- `CODE_BLOCK`;
- `CALLOUT`;
- `FOOTER`;
- `CLASSIFICATION_MARKING`;
- `PROVENANCE_NOTE`.

Each block binds exact approved content and the provenance references needed to justify material claims.

## `PresentationSlide`

A candidate slide contains:

- stable slide key;
- ordered presentation blocks;
- explicit layout reference;
- explicit notes content when approved;
- explicit asset references;
- explicit accessibility metadata when used;
- exact source/provenance bindings;
- explicit classification marking rules.

Slide order is semantic and must be explicit.

## `PresentationRenderPlan`

Required candidate fields:

- `render_source_binding`;
- `artifact_kind`;
- `artifact_version`;
- ordered `slides`;
- `assets`;
- `template_binding`;
- `render_profile`;
- presentation title;
- presentation subject;
- approved speaker-note content where present;
- deterministic allowed metadata fields.

For this amendment:

```text
artifact_kind=PPTX
```

The plan contains already approved presentation meaning.

The renderer must not add, delete, reorder, summarize, rewrite, or reinterpret material content except where an explicitly approved deterministic layout rule requires a non-semantic formatting transformation.

## Presentation render-plan identity

Candidate rule:

```text
presentation_render_plan_hash =
SHA256(canonical(PresentationRenderPlan))
```

Candidate external form:

```text
presentation-render-plan:sha256:<64 lowercase hex>
```

The plan hash excludes ambient runtime state.

## `ArtifactRenderRequest`

A common rendering envelope may bind:

- render-plan type;
- render-plan hash;
- artifact kind;
- renderer identity;
- renderer version;
- render-profile hash.

Candidate identity:

```text
artifact_render_request_id =
SHA256(canonical(ArtifactRenderRequest))
```

The envelope may support:

- `DocumentRenderPlan` for DOCX/PDF;
- `PresentationRenderPlan` for PPTX.

The plan types remain semantically distinct.

## PPTX `RenderResult`

A successful PPTX render result requires at least:

- `artifact_render_request_id`;
- `presentation_render_plan_hash`;
- `artifact_id`;
- `artifact_version`;
- `artifact_kind=PPTX`;
- `artifact_sha256`;
- `artifact_size_bytes`;
- generation-profile identity/hash;
- render-trace hash;
- deterministic validation evidence.

`RENDERED` means only that exact internal PPTX bytes were generated.

It does not mean export authorized, presentation delivered, or client receipt established.

## Artifact identity

The final exact PPTX SHA-256 participates in artifact identity.

Any byte change requires a different artifact hash and artifact identity.

A later V3.7 artifact descriptor must be constructible without semantic reinterpretation.

## Speaker notes

Speaker-note meaning belongs to V3.9 composition.

V3.8 may render only speaker-note bytes that are explicitly present in the approved `PresentationRenderPlan`.

V3.8 may not infer, summarize, expand, or generate speaker notes.

## Charts and diagrams

Chart values and chart-data workbooks, when present, are governed inputs.

They must be:

- explicit;
- provenance-aware where they represent material claims;
- hash-bound;
- deterministic;
- tenant-bound;
- free of unapproved external data connections.

A diagram rendered from approved vector or raster bytes is treated as a hash-bound asset.

A diagram rendered from a deterministic declarative specification must bind the exact specification and renderer identity.

## Cross-format authority parity

DOCX, PDF, and PPTX may differ structurally and visually.

They may not silently diverge on:

- protected authoritative facts;
- provenance;
- classification;
- approval binding;
- tenant/engagement identity;
- artifact-specific identity.

Cross-format byte or layout identity is not required.

## Authority boundary

These contracts prove deterministic binding. They do not create:

- source truth;
- approval;
- export authorization;
- client release;
- V3.9 presentation-composition authority;
- implementation authority.
