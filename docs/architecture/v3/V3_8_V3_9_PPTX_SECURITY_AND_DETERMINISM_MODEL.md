# Humanize V3.8 / V3.9 - PPTX Security and Determinism Model R1

## Status

Detached architecture-amendment candidate only.

This model extends the accepted V3.8 security and deterministic-rendering posture to PPTX without granting runtime authority.

## Security objective

A governed PPTX renderer must generate exact, reproducible, internally controlled presentation bytes without weakening:

- tenant isolation;
- engagement binding;
- source authority;
- protected facts;
- provenance;
- classification;
- approval state;
- V3.7 export authorization;
- exact artifact identity.

## Deterministic OOXML package boundary

PPTX is an Office Open XML package. Determinism therefore applies to the complete package, not only visible slide content.

A qualified renderer must control or normalize every byte-affecting element, including:

- ZIP entry ordering;
- ZIP timestamps and flags;
- content-type declarations;
- package properties;
- presentation properties;
- slide ordering;
- slide identifiers;
- relationship identifiers;
- master identifiers;
- layout identifiers;
- theme identity;
- embedded font behavior;
- media filenames and package paths;
- notes-slide relationships;
- chart relationships;
- chart-data workbook bytes;
- generated XML ordering where semantically irrelevant ordering could drift;
- document metadata;
- application metadata;
- custom properties;
- compression behavior where it affects final bytes.

Current time, host identity, process ID, temporary paths, random IDs, locale defaults, and mutable user-profile state must not silently influence final PPTX bytes.

## Renderer and toolchain pinning

Qualification must bind:

- renderer identity;
- renderer version;
- runtime version;
- normalization version;
- template hash;
- theme hash;
- font-set hash;
- all asset hashes;
- render-profile hash.

If the selected renderer or supporting library cannot produce stable bytes under the supported environment, qualification fails closed.

## Active content

The following are prohibited by default:

- VBA macros;
- macro-enabled PPTM behavior;
- ActiveX;
- OLE executable objects;
- launch actions;
- embedded executables;
- unsafe package parts;
- scripts;
- unapproved embedded files.

A PPTX renderer must not silently emit a macro-enabled package.

## External references

The renderer core is network-free.

The following are prohibited:

- external template dependencies;
- remote image fetching;
- remote media fetching;
- linked chart data that requires network access;
- external data connections;
- unapproved hyperlinks that trigger automatic fetch behavior;
- external relationships used as render inputs.

Any required external resource must first be materialized, security-checked, and hash-bound through an authorized upstream process.

## Fonts and layout

Fonts are byte- and layout-affecting inputs.

A qualified profile must either:

- pin the exact supported font set; or
- define and qualify deterministic substitution behavior.

Silent host-dependent font substitution is prohibited.

Theme, master, layout, slide size, margins, placeholder geometry, and text-fit policy must be explicit when they affect output.

## Media

Images and other media must be:

- materialized before rendering;
- hash-bound;
- media-type validated;
- size/dimension validated where policy requires;
- free of unsafe active payloads;
- deterministically named or normalized inside the package.

Image metadata must not introduce nondeterministic bytes unless explicitly normalized.

## Charts

If charts are present:

- source values are explicit governed inputs;
- chart-data workbook bytes are deterministic and hash-bound;
- worksheet ordering and metadata are deterministic;
- no external workbook links are allowed;
- no external data refresh is allowed;
- number formatting is explicit;
- locale-sensitive formatting is prohibited unless explicitly bound.

## Speaker notes and comments

Approved speaker notes may be rendered.

The renderer must not synthesize notes.

Comments, review annotations, and authoring-history metadata are excluded unless a later architecture amendment explicitly governs them.

Unapproved comments or authoring metadata fail validation.

## Metadata minimization

PPTX metadata must not leak:

- workstation names;
- local file paths;
- usernames;
- organization-private editor identities;
- temporary directories;
- nondeterministic timestamps;
- build-host metadata.

Only explicitly allowed, deterministic metadata may remain.

## Path and package safety

The renderer must fail closed on:

- path traversal;
- symbolic-link escape while reading local render inputs;
- package-entry path escape;
- duplicate conflicting package parts;
- malformed relationships;
- unexpected content types;
- unexpected embedded objects;
- unsupported package extensions.

## Protected facts and provenance

Formatting must never change protected authoritative facts.

Presentation compression, layout, or visual adaptation must not convert:

- assumptions into facts;
- failed evaluations into passes;
- risks into approvals;
- unapproved architecture alternatives into accepted decisions.

Material presentation claims remain traceable to authoritative evidence or are explicitly classified as presentation-only content.

## V3.7 artifact binding

The final normalized PPTX bytes are hashed before artifact-specific V3.7 authorization.

Any later byte change requires:

- a new artifact SHA-256;
- a new artifact identity;
- re-evaluation by the V3.7 authorization boundary.

## Required post-render validation

A qualified implementation must plan deterministic validation of:

- package structure;
- expected slide count and order;
- expected masters/layouts/themes;
- absence of prohibited active content;
- absence of prohibited external relationships;
- exact required classification markings;
- exact approved notes presence/absence;
- asset hashes where recoverable;
- final artifact SHA-256;
- artifact descriptor construction.

## Failure posture

The renderer fails closed when:

- deterministic output cannot be proven;
- an input hash mismatches;
- approval binding is absent or stale;
- tenant or engagement identity mismatches;
- required provenance is missing;
- classification would be weakened;
- prohibited active content appears;
- prohibited external relationships appear;
- host state changes final bytes;
- renderer/toolchain identity is not approved;
- validation cannot prove the required package invariants.

## Non-authority

This security model grants no implementation, runtime rendering, export, client release, deployment, dependency installation, or V3.9 composition authority.
