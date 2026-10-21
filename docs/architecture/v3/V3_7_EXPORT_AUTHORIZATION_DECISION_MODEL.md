# Humanize V3.7 - Export Authorization Decision Model R1

## Status

Detached architecture planning candidate only. This document plans deterministic authorization semantics; it does not execute an export or release a client artifact.

## Decision objective

The V3.7 evaluator answers:

> Is this exact immutable manifest subject authorized for this exact audience and delivery context under this exact export policy and exact accepted predecessor authority?

It does not answer:

> Has the artifact been delivered to the client?

## Decision inputs

The evaluator requires an exact:

- manifest subject and `manifest_subject_hash`;
- normalized artifact identity/version/hash set;
- tenant and engagement binding;
- source bundle identity/version;
- provenance set;
- classification;
- V3.6 approval binding;
- source disposition;
- intended audience;
- allowed delivery context;
- export policy identity/hash and policy contents.

## Evaluation precedence

A later implementation should preserve this fail-closed precedence:

1. malformed manifest subject -> `ERROR`
2. malformed export request -> `ERROR`
3. manifest-subject hash mismatch -> `ERROR`
4. tenant mismatch -> `ERROR`
5. engagement mismatch -> `ERROR`
6. artifact-set mismatch -> `ERROR`
7. artifact identity/version/hash conflict -> `ERROR`
8. source-bundle identity/version mismatch -> `ERROR`
9. missing or contradictory provenance -> `ERROR`
10. classification missing or inconsistent -> `ERROR`
11. V3.6 approval binding malformed -> `ERROR`
12. V3.6 approval request/composition mismatch -> `ERROR`
13. approval state other than `APPROVED` -> `DENIED`
14. export policy malformed or identity mismatch -> `ERROR`
15. source disposition not policy-permitted -> `DENIED`
16. classification not policy-permitted -> `DENIED`
17. intended audience missing or not policy-permitted -> `DENIED`
18. delivery context missing or not policy-permitted -> `DENIED`
19. all exact checks satisfied -> `AUTHORIZED`

No later rule may convert an earlier structural or authority error into authorization.

## Necessary but not sufficient approval

V3.6 `APPROVED` is necessary for export authorization but is not sufficient by itself.

The following must remain true:

```text
V3_6_APPROVED
!=
ARTIFACT_GENERATED

V3_6_APPROVED
!=
EXPORT_AUTHORIZED

ARTIFACT_GENERATED
!=
EXPORT_AUTHORIZED

EXPORT_AUTHORIZED
!=
CLIENT_RELEASED
```

## `PRESENTATION_ONLY` semantics

A V3.6 approval of a V3.5 `PRESENTATION_ONLY` composition does not convert it into authoritative source truth.

A later export policy may explicitly permit or deny presentation-only delivery contexts. If permitted, the final manifest must preserve `source_disposition=PRESENTATION_ONLY` and all provenance/classification constraints.

## Denied versus error

`DENIED` is a valid policy outcome for structurally valid, consistently bound evidence that does not satisfy explicit export policy.

Examples:

- approval not complete;
- classification not permitted for the delivery context;
- audience not permitted;
- delivery context not permitted;
- source disposition not permitted.

`ERROR` represents invalid, contradictory, stale, ambiguous, or authority-inconsistent evidence.

Examples:

- tenant mismatch;
- stale approval binding;
- artifact hash mismatch;
- manifest hash mismatch;
- policy hash mismatch;
- conflicting duplicate artifact identity;
- missing required provenance.

No `ERROR` may be silently downgraded to `DENIED` or `AUTHORIZED` if doing so would hide integrity or authority failure.

## Deterministic policy evaluation

Core decision semantics must not depend on:

- current time;
- random values;
- provider availability;
- network responses;
- mutable filesystem state;
- database state;
- request arrival order;
- locale;
- process identity.

Equivalent logical inputs must produce the same normalized request identity, decision, failure set, decision identity, and trace hash.

## Replay and staleness

An export decision is valid only for the exact `manifest_subject_hash` and exact policy identity contained in its request.

Any change to:

- artifact bytes/hash;
- artifact version;
- source bundle identity/version;
- provenance;
- classification;
- approval binding;
- audience;
- delivery context;
- policy identity/hash;

requires a new export request identity and a new decision.

Old authorization may remain historical evidence but is stale for the changed subject.

## Final-manifest construction rule

The final manifest records the export decision only after decision evaluation completes.

This yields:

```text
MANIFEST_SUBJECT
-> EXPORT_AUTHORIZATION_REQUEST
-> EXPORT_AUTHORIZATION_DECISION
-> FINAL_DELIVERY_MANIFEST
```

The final manifest is an evidence record of the exact decision. It is not itself a transport action.

## Client-release boundary

No V3.7 decision may execute or imply:

- upload;
- email;
- download publication;
- external share creation;
- storage-provider ACL change;
- destination connector invocation;
- client notification;
- client release.

Those actions require separately reviewed authority outside this architecture candidate.
