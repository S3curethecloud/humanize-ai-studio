# Humanize V3.8 - Rendering Contracts and Identity R1

## Status

Architecture planning candidate only. Contract names are semantic planning names, not authorized runtime types.

## `RenderSourceBinding`

Required fields:

- `tenant_id`
- `engagement_id`
- `source_bundle_id`
- `source_bundle_version`
- `composition_id`
- `composition_hash`
- `source_disposition`
- `classification`
- `approval_request_id`
- `approval_trace_hash`
- `approval_state`
- `provenance_refs`

Rules:

- `approval_state` must be exact V3.6 `APPROVED` for render eligibility;
- source disposition remains unchanged;
- classification remains unchanged unless a separately authorized stronger handling label is explicitly bound;
- provenance references are unique and canonically ordered;
- tenant/engagement mismatch fails closed.

## `RenderAsset`

Required fields:

- `asset_id`
- `asset_kind`
- `asset_version`
- `asset_sha256`
- `media_type`

Optional planning fields may include deterministic dimensions or accessibility metadata.

Rules:

- asset bytes must be materialized before rendering;
- network URLs are not authoritative asset inputs;
- every asset is hash-bound;
- duplicate identity/version with conflicting hashes fails closed;
- unsupported media types fail closed.

## `RenderTemplateBinding`

Required semantic fields when a template is used:

- `template_id`
- `template_version`
- `template_sha256`
- `template_kind`

Rules:

- templates are immutable render inputs;
- external template references are prohibited;
- macros, executable objects, or active content are prohibited;
- changed template bytes require a new template hash and render-plan identity.

## `RenderProfile`

A render profile binds every controlled byte-affecting policy decision.

Candidate fields:

- `render_profile_id`
- `render_profile_version`
- `render_profile_hash`
- `page_size`
- `margins`
- `default_styles`
- `font_set_id`
- `font_set_hash`
- `metadata_policy_id`
- `metadata_policy_hash`
- `renderer_id`
- `renderer_version`
- `normalizer_id`
- `normalizer_version`

Rules:

- all identity-participating values are explicit;
- locale and timezone are explicit if they affect output;
- current time is never inferred;
- missing required renderer/font/template identity fails closed.

## `DocumentBlock`

Candidate block kinds:

- `HEADING`
- `PARAGRAPH`
- `BULLET_LIST`
- `NUMBERED_LIST`
- `TABLE`
- `IMAGE`
- `CODE_BLOCK`
- `PAGE_BREAK`
- `CLASSIFICATION_MARKING`
- `PROVENANCE_NOTE`

Each block binds stable content and the source/provenance references needed to prove authority where applicable.

## `DocumentRenderPlan`

Required semantic fields:

- `render_source_binding`
- `artifact_kind`
- `artifact_version`
- `ordered_blocks`
- `assets`
- `template_binding`
- `render_profile`
- `document_title`
- `document_subject`
- deterministic allowed metadata fields

`artifact_kind` is exactly `DOCX` or `PDF` in V3.8.

### Render-plan identity

Candidate rule:

`render_plan_hash = SHA256(canonical(DocumentRenderPlan))`

Candidate external form:

`render-plan:sha256:<64 lowercase hex>`

The plan hash excludes ambient runtime state.

## `RenderRequest`

A render request binds one exact render plan and one exact requested output format.

Required fields:

- `render_plan_hash`
- `artifact_kind`
- `renderer_id`
- `renderer_version`
- `render_profile_hash`

Candidate identity:

`render_request_id = SHA256(canonical(RenderRequest))`

## `RenderResult`

Candidate result states:

- `RENDERED`
- `DENIED`
- `ERROR`

Required semantic fields for `RENDERED`:

- `render_request_id`
- `render_plan_hash`
- `artifact_id`
- `artifact_version`
- `artifact_kind`
- `artifact_sha256`
- `artifact_size_bytes`
- `generation_profile_id`
- `generation_profile_hash`
- `render_trace_hash`

`RENDERED` means exact artifact bytes were generated internally. It does not mean export authorized or client released.

## Artifact identity

Candidate artifact identity rule:

`artifact_id = "artifact:sha256:" + SHA256(canonical(render_plan_hash + artifact_kind + artifact_version + artifact_sha256))`

The exact final artifact SHA-256 participates in final artifact identity.

Any byte change requires a new artifact identity.

## V3.7 artifact descriptor compatibility

A successful V3.8 render result must be convertible without semantic reinterpretation into the V3.7 artifact descriptor fields:

- `artifact_id`
- `artifact_version`
- `artifact_sha256`
- `artifact_kind`
- `source_composition_id`
- `source_composition_hash`

Generation metadata must expose deterministic generator/profile bindings required by V3.7.

## Canonical ordering

- UTF-8 for canonical textual identity serialization;
- stable key ordering;
- arrays ordered by explicit sequence where order is semantic;
- sets unique and lexicographically ordered;
- assets ordered by `(asset_id, asset_version, asset_sha256)`;
- provenance references unique and lexicographically ordered;
- no locale-sensitive transforms;
- no object-memory representation;
- no host path in identity.

## Authority boundary

Hashes prove exact binding of supplied inputs and generated bytes. They do not create source truth, approval, export authorization, client release, or receipt evidence.
