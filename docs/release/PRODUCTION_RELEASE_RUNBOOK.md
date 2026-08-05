# Humanize AI Studio Production Release Runbook

## Preconditions

Before deployment:

1. Work from the repository root.
2. Confirm the intended branch is checked out.
3. Confirm the working tree contains only the approved release changes.
4. Confirm the deterministic evaluation report passes.
5. Never paste Cloudflare credentials or API tokens into terminal output,
   issue comments, documentation, or chat transcripts.

## Local API gate

From `apps/api`:

```bash
ruff check . --fix
ruff format .
ruff check .
mypy app tests
pytest -q
python -m app.evaluation \
  --output artifacts/evaluation/quality-evaluation.json

Required outcome:

Ruff passes;
mypy passes;
all tests pass;
evaluation CLI prints Release gate: PASS.
Web and Cloudflare validation

From the repository root:

npm run build:web
npm run cf:typecheck
npx wrangler deploy --dry-run

Required outcome:

frontend TypeScript compilation passes;
Vite production build passes;
Cloudflare runtime types generate successfully;
Cloudflare TypeScript validation passes;
dry-run container image build succeeds.
Fresh production deployment

To avoid stale container-image reuse:

docker builder prune --all --force
npm run build:web
npm run cf:typecheck
npx wrangler deploy --dry-run
npx wrangler deploy

The deployment must show:

a new image digest;
EDIT humanize-ai-studio-humanizeapicontainer;
SUCCESS Modified application;
a new Worker version ID.
Readiness verification
export HUMANIZE_URL='https://humanize.securethecloud.dev'

curl --fail --silent --show-error \
  "$HUMANIZE_URL/ready?release=increment-8" \
  | python3 -m json.tool

Expected response:

{
  "status": "ready",
  "service": "humanize-ai-studio-api",
  "configured_provider": "cloudflare",
  "active_provider": "cloudflare-workers-ai-with-fallback"
}

A transient HTTP 500 during container rollout may be retried after the new
container becomes healthy. Repeated 500 responses require log inspection and
must not be treated as a successful release.

Production rewrite verification

Use a unique request ID for every production verification.

Required request characteristics:

deep_reconstruction;
explicit audience and tone;
protected qualification phrase;
multi-sentence source;
sufficiently complex content to exercise structural enforcement.

Accept either:

compliant Cloudflare provider output; or
controlled deterministic fallback.

Reject:

stale prompt or deployment markers;
unsupported claim expansion;
lexical-only deep reconstruction;
provider failure without controlled fallback;
an unchanged provider output presented as successful reconstruction.
Rollback conditions

Rollback or halt the release when:

readiness remains unavailable;
the production request returns an uncontrolled 5xx response;
an unsafe provider output is released;
a deep reconstruction bypasses structural validation;
the evaluation release gate fails;
more than two model calls are observed;
the deployed image digest does not match the intended release deployment.
Evidence retention

Retain:

evaluation JSON;
full local gate output;
image digest;
Worker version ID;
readiness response;
production rewrite response;
final commit SHA;
release tag.

Do not retain secrets.
