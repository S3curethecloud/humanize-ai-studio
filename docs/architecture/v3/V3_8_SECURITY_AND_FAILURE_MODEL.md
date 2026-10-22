# Humanize V3.8 - Security and Failure Model R1

## Status

Architecture planning candidate only.

## Security objective

V3.8 must generate DOCX/PDF artifact bytes without weakening source authority, tenant isolation, classification, approval state, provenance, V3.7 export boundaries, or deterministic artifact identity.

## Threats and required response

### Cross-tenant rendering

Threat: source evidence, assets, templates, or approvals from tenant A are rendered for tenant B.

Required response: exact mismatch -> `ERROR`.

### Cross-engagement rendering

Threat: content or approval from one engagement is reused in another.

Required response: exact mismatch -> `ERROR`.

### Stale approval replay

Threat: a V3.6 approval for old composition bytes is used for a changed composition.

Required response: composition/request/hash mismatch -> `ERROR`.

### Artifact substitution

Threat: a previously authorized artifact identity is paired with changed bytes.

Required response: changed bytes -> changed SHA-256 -> changed artifact identity; prior V3.7 authorization is stale.

### Template substitution

Threat: template identity is preserved while template bytes change.

Required response: template hash mismatch -> `ERROR`.

### Asset substitution

Threat: an image or other embedded asset changes under the same identity/version.

Required response: asset hash mismatch -> `ERROR`.

### External resource injection

Threat: renderer fetches fonts, images, styles, templates, or other content from network locations.

Required response: rendering core uses only pre-materialized hash-bound resources; unresolved external dependency -> `ERROR`.

### Path traversal

Threat: a render asset/template path escapes the authorized workspace.

Required response: reject traversal, absolute-path escape, and symbolic-link escape.

### DOCX active content

Threat: generated DOCX contains macros, OLE payloads, external templates, or auto-fetch relationships.

Required response: prohibited content -> `ERROR`.

### PDF active behavior

Threat: generated PDF contains JavaScript, launch actions, unapproved embedded files, or unsafe external actions.

Required response: prohibited content -> `ERROR`.

### Classification stripping

Threat: rendering or conversion omits mandatory classification markings.

Required response: validation failure -> `ERROR`.

### Provenance stripping

Threat: required provenance/evidence mapping is lost during composition-to-render conversion.

Required response: missing required binding -> `ERROR`.

### Font substitution drift

Threat: ambient font availability changes layout or bytes.

Required response: use pinned font-set identity/hash or fail qualification; silent substitution is prohibited unless an explicit qualified profile defines it.

### Timestamp nondeterminism

Threat: current time enters DOCX ZIP metadata, document properties, PDF metadata, or IDs.

Required response: normalize to explicit deterministic values or exclude volatile data from governed bytes where the format/toolchain permits; unqualified nondeterminism -> `ERROR`.

### Random identifier drift

Threat: relationships, package IDs, PDF IDs, or internal object identifiers are random.

Required response: deterministic assignment/normalization required.

### Locale drift

Threat: host locale changes dates, numbers, fonts, hyphenation, or other byte-affecting output.

Required response: locale must be explicit and qualified when relevant.

### Toolchain drift

Threat: renderer upgrade changes bytes under the same generation profile.

Required response: renderer/toolchain version participates in generation profile; changed version requires new profile identity and requalification.

### Partial artifact leakage

Threat: renderer error leaves a partial file that is mistaken for governed output.

Required response: partial output is non-authoritative and never returned with `RENDERED` status.

### Export-authority laundering

Threat: local file existence or successful rendering is presented as export authorization.

Required response: prohibited. Only exact V3.7 authorization bound to the final artifact descriptor may establish export authorization.

### Client-release escalation

Threat: `RENDERED` or V3.7 `AUTHORIZED` is treated as proof of client receipt.

Required response: prohibited. Client release remains separately governed.

## Fail-closed characteristics

- malformed request -> `ERROR`;
- authority mismatch -> `ERROR`;
- integrity mismatch -> `ERROR`;
- stale binding -> `ERROR`;
- unsafe active content -> `ERROR`;
- nondeterministic unqualified output -> `ERROR`;
- missing required approval -> `DENIED` or `ERROR` according to structural validity;
- no last-write-wins conflict resolution;
- no successful artifact on partial failure;
- no network fallback;
- no silent font/template/asset substitution;
- no automatic release.

## Sensitive-data handling

Rendering must preserve existing classification and tenant boundaries. Temporary render material must be bounded to an authorized workspace and cleaned according to a later separately approved implementation policy.

No architecture candidate grants authority to upload content to third-party renderers or external conversion services.

## Audit evidence requirements

Qualification must preserve evidence for:

- exact source bindings;
- exact approval binding;
- exact render plan;
- exact templates/assets/fonts;
- exact toolchain versions;
- exact normalization behavior;
- security validation results;
- final artifact hash and size;
- cross-format semantic consistency where both formats are generated;
- V3.7 descriptor compatibility;
- no external release side effect.
