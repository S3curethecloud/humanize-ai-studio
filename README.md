# Humanize AI Studio

Humanize AI Studio is a meaning-preserving, voice-aware editorial rewriting
platform.

It improves clarity, naturalness, structure, and audience fit while enforcing
claim integrity, qualification preservation, intensity-specific rewrite
distance, controlled provider repair, and deterministic fallback.

## Core safeguards

- Claim-preserving rewriting
- Qualification and participation-boundary protection
- No unsupported expertise, ownership, seniority, or impact inflation
- Intensity-specific rewrite-distance validation
- Structural enforcement for deep reconstruction
- At most one repair request
- Deterministic fail-closed fallback
- Machine-readable quality release gate

## Repository structure

- `apps/api` — FastAPI rewrite and verification service
- `apps/web` — React and Vite user interface
- `cloudflare` — Worker and container routing
- `docs/release` — release contract, runbook, and code-freeze policy

## Local API validation

```bash
cd apps/api

ruff check . --fix
ruff format .
ruff check .
mypy app tests
pytest -q

python -m app.evaluation \
  --output artifacts/evaluation/quality-evaluation.json
Web and Cloudflare validation

From the repository root:

npm run build:web
npm run cf:typecheck
npx wrangler deploy --dry-run
Release documentation
Quality-hardening release contract
Production release runbook
Quality-hardening code freeze
Production

Production endpoint:

https://humanize.securethecloud.dev

The production deployment uses Cloudflare Workers AI with deterministic
fallback when provider output fails safety or quality validation.

## Final release gate

The final quality-hardening release gate runs the complete API gate,
regenerates and validates deterministic evaluation evidence, builds the
frontend, validates Cloudflare types, and executes a Cloudflare deployment
dry run.

From the repository root:

```bash
npm run release:gate

A valid release candidate must end with:

FINAL RELEASE GATE: PASS

The gate writes its machine-readable result to:

apps/api/artifacts/release/final-release-gate.json
