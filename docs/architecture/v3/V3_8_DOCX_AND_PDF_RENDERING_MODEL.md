# Humanize V3.8 - DOCX and PDF Rendering Model R1

## Status

Architecture planning candidate only.

## Rendering pipeline

A later implementation should preserve this bounded pipeline:

```text
accepted governed source binding
-> validate render eligibility
-> canonicalize DocumentRenderPlan
-> resolve only hash-bound local assets/templates/fonts
-> render format-specific candidate
-> normalize volatile format metadata
-> validate security and semantic invariants
-> compute final artifact SHA-256
-> construct V3.8 RenderResult / V3.7 artifact descriptor
-> stop before external release
```

## Eligibility evaluation precedence

1. malformed source binding -> `ERROR`
2. tenant mismatch -> `ERROR`
3. engagement mismatch -> `ERROR`
4. source composition/hash mismatch -> `ERROR`
5. V3.6 approval binding malformed -> `ERROR`
6. approval state other than `APPROVED` -> `DENIED`
7. missing required provenance -> `ERROR`
8. classification missing/inconsistent -> `ERROR`
9. render-plan hash mismatch -> `ERROR`
10. unknown or unpinned render profile -> `ERROR`
11. unknown renderer version -> `ERROR`
12. unknown font set where required -> `ERROR`
13. missing or hash-mismatched template/asset -> `ERROR`
14. unsupported artifact kind -> `ERROR`
15. all exact checks satisfied -> render candidate may proceed

No later step may convert an earlier authority or integrity error into success.

## DOCX model

DOCX generation must treat the Office Open XML package as a deterministic artifact, not merely as a semantically equivalent document.

A later implementation must control or normalize at least:

- package part set;
- package part paths;
- content-types declarations;
- relationships;
- style identifiers;
- numbering identifiers;
- document properties;
- ZIP member ordering;
- ZIP member timestamps;
- compression behavior to the extent required for stable bytes;
- media part names and hashes;
- field behavior that could update on open.

The renderer must not include macros, OLE executable payloads, external templates, external images, external hyperlinks that auto-fetch, or other active content not explicitly permitted by a future policy.

## PDF model

PDF generation must use a qualified deterministic toolchain.

A later implementation must control or normalize at least:

- page geometry;
- font selection and embedding;
- image encoding;
- metadata dictionaries;
- creation/modification timestamps;
- document IDs;
- producer/creator metadata where byte-affecting;
- object/xref ordering where toolchain behavior exposes it;
- compression settings where byte-affecting;
- hyperlinks/actions;
- embedded files;
- JavaScript or launch actions.

The supported environment must be explicitly qualified. Cross-platform byte equality must not be claimed unless proven.

## Shared semantic plan

DOCX and PDF must derive from the same `DocumentRenderPlan` when they represent the same client document.

Allowed format-specific differences include only explicit render-profile behavior such as pagination, line wrapping, page-number placement, or format-specific metadata.

The following may not differ between formats:

- authoritative facts;
- qualification language;
- classification;
- approval binding;
- tenant/engagement identity;
- provenance mapping;
- included/excluded sections unless the render plan explicitly declares a format-specific presentation rule.

## Artifact finalization

Artifact bytes are final only after format normalization and security validation complete.

The finalization sequence is:

```text
raw renderer output
-> format normalization
-> security validation
-> semantic binding validation
-> final bytes
-> SHA-256
-> artifact identity
```

Hashing pre-normalization bytes is prohibited for final V3.7 artifact descriptors.

## Export authorization interaction

V3.8 rendering precedes artifact-specific V3.7 export authorization because V3.7 binds the exact final artifact hash.

A generated artifact therefore begins as an internal candidate.

After V3.8 emits its exact artifact descriptor, V3.7 may construct the manifest subject and evaluate export authorization.

A later downstream workflow may associate the resulting V3.7 authorization with the exact artifact. Any artifact byte change makes that authorization stale.

V3.8 itself does not release the artifact to a client.

## Failure semantics

`DENIED` is reserved for structurally valid render requests that lack required approval eligibility.

`ERROR` covers malformed, contradictory, stale, nondeterministic, unsafe, or authority-inconsistent inputs/output.

A partial file produced during an `ERROR` is non-authoritative and must not be returned as a successful governed artifact.

## Evidence trace

A successful render trace must preserve at least:

- render request identity;
- render plan hash;
- source composition identity/hash;
- approval request identity/trace hash;
- classification;
- provenance references;
- template identity/hash;
- asset identities/hashes;
- render profile identity/hash;
- renderer/toolchain identity/version;
- font-set identity/hash where applicable;
- normalization identity/version;
- artifact kind/version;
- final artifact SHA-256;
- final artifact size;
- normalized warnings/failure codes;
- render trace hash.

The trace proves how exact bytes were derived from exact governed inputs. It does not prove export authorization or client receipt.
