# Humanize AI Studio Quality-Hardening Release

## Release status

This document defines the final quality-hardening release contract for
Humanize AI Studio.

The quality-hardening program ends with Increment 8. Subsequent changes
are maintenance, defect correction, operational improvement, or separately
approved product development. They are not additional quality-hardening
increments.

## Product objective

Humanize AI Studio performs meaning-preserving, voice-aware editorial
rewriting.

The system is not designed to bypass AI-content detectors, conceal
authorship, fabricate experience, strengthen claims, or invent outcomes.

## Enforced rewrite contract

Every released rewrite must preserve:

- meaning;
- factual claims;
- qualifications;
- uncertainty and negation;
- level of experience;
- ownership and participation boundaries;
- numbers and dates when preservation is requested;
- technical terms and named entities where applicable.

The system must reject or safely fall back when a provider output:

- inflates expertise, ownership, seniority, scope, certainty, or impact;
- removes a protected qualification;
- invents a claim, outcome, metric, credential, or responsibility;
- fails the useful rewrite-distance contract;
- fails deep-reconstruction structural requirements;
- ignores the required structural repair blueprint.

## Rewrite intensity contract

### Light edit

A light edit requires a textual change. It may make grammar, punctuation,
clarity, or minor wording improvements.

### Natural rewrite

A natural rewrite requires at least one meaningful lexical change.

### Deep reconstruction

A deep reconstruction requires:

1. at least one meaningful lexical change; and
2. either:
   - a sentence-count change; or
   - material information-order movement.

When a deep-reconstruction repair is required, the repaired output must
also follow the deterministic structural blueprint supplied to the model.

## Provider execution contract

The provider path permits:

1. one initial model request;
2. at most one policy-constrained repair request.

A third model request is forbidden.

When the provider cannot return a compliant output, the system must use
the deterministic fallback path rather than release the rejected output.

## Release thresholds

The deterministic performance cohort must satisfy:

- provider success rate: at least 0.70;
- repair success rate: at least 0.50 when repairs are attempted;
- fallback rate: no more than 0.30;
- maximum model calls per case: 2;
- unsafe output releases: 0;
- deep structural failure releases: 0.

The deterministic safety-control cohort must satisfy:

- every case fails closed through controlled fallback;
- unsafe output releases: 0;
- maximum model calls per case: 2.

The combined machine-readable release gate must report `passed: true`.

## Required release evidence

A release candidate is eligible only when all of the following pass:

- Ruff formatting and linting;
- strict mypy validation;
- complete pytest suite;
- deterministic evaluation report generation;
- machine-readable release gate;
- frontend production build;
- Cloudflare TypeScript validation;
- Cloudflare dry-run deployment;
- production readiness endpoint;
- production rewrite acceptance test;
- clean Git working tree after final commit.

## Production acceptance paths

### Preferred provider path

The production response may be accepted when:

- the active provider is Cloudflare Workers AI;
- fallback is false;
- the output preserves the source claims;
- the output satisfies the requested rewrite intensity;
- deep reconstruction visibly changes structure or information order.

### Safe terminal path

The production response may be accepted as safe terminal behavior when:

- the primary provider is Cloudflare Workers AI;
- the actual provider is deterministic;
- fallback is true;
- the provider error category is controlled;
- the rejected provider output is not released.

Safe terminal acceptance proves enforcement. It does not prove that the
model consistently produces desirable structural rewrites.

## Code-freeze policy

After Increment 8 is released:

- claim-integrity rules must not be weakened without explicit review;
- rewrite-distance thresholds must not be weakened to improve success rate;
- blueprint-adherence validation must not be removed;
- the two-call maximum must not be increased without explicit review;
- evaluation release thresholds must not be reduced silently;
- generated evaluation evidence must be updated when the corpus,
  evaluator, thresholds, or provider contract changes;
- prompt-version changes must be explicit and covered by tests;
- production provider and fallback behavior must remain observable.

## Known nonblocking issue

The test suite currently reports a Starlette deprecation warning concerning
the legacy `httpx` integration used by `starlette.testclient`.

This warning is nonblocking for the quality-hardening release, but should be
resolved as a maintenance dependency update rather than ignored indefinitely.
