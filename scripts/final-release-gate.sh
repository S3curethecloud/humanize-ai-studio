#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1
  pwd
)"
API_DIR="$REPO_ROOT/apps/api"
EVALUATION_REPORT="$API_DIR/artifacts/evaluation/quality-evaluation.json"
FINAL_REPORT="$API_DIR/artifacts/release/final-release-gate.json"

log() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf '\nFINAL RELEASE GATE: FAIL\n' >&2
  printf '%s\n' "$1" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3 is required."
command -v npm >/dev/null 2>&1 || fail "npm is required."
command -v npx >/dev/null 2>&1 || fail "npx is required."

log "Running API formatting and lint checks"
cd "$API_DIR"
ruff check . --fix
ruff format .
ruff check .

log "Running strict type validation"
mypy app tests

log "Running complete API test suite"
pytest -q

log "Generating deterministic evaluation report"
python3 -m app.evaluation \
  --output "$EVALUATION_REPORT"

log "Validating deterministic release evidence"
python3 - "$EVALUATION_REPORT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text(encoding="utf-8"))

if report.get("schema_version") != "humanize-evaluation-v2":
    raise SystemExit(
        "Unexpected evaluation schema version: "
        f"{report.get('schema_version')!r}"
    )

release_gate = report.get("release_gate")

if not isinstance(release_gate, dict):
    raise SystemExit("Evaluation release gate is missing or invalid.")

if release_gate.get("passed") is not True:
    raise SystemExit(
        "Evaluation release gate failed: "
        f"{release_gate.get('failures')!r}"
    )

performance = report.get("performance_summary")
safety = report.get("safety_control_gate")

if not isinstance(performance, dict):
    raise SystemExit("Performance summary is missing or invalid.")

if not isinstance(safety, dict):
    raise SystemExit("Safety-control gate is missing or invalid.")

required_performance = {
    "provider_success_rate": 1.0,
    "repair_success_rate": 1.0,
    "fallback_rate": 0.0,
}

for key, expected in required_performance.items():
    actual = performance.get(key)

    if actual != expected:
        raise SystemExit(
            f"Performance metric {key}={actual!r}; "
            f"expected {expected!r}."
        )

if safety.get("controlled_fallback_count") != 3:
    raise SystemExit(
        "Safety-control fallback count must equal 3."
    )

if safety.get("unsafe_output_release_count") != 0:
    raise SystemExit(
        "Unsafe output release count must equal 0."
    )

if safety.get("maximum_observed_model_call_count") != 2:
    raise SystemExit(
        "Maximum observed model-call count must equal 2."
    )

print("Deterministic evaluation evidence: PASS")
PY

log "Building frontend"
cd "$REPO_ROOT"
npm run build:web

log "Running Cloudflare type validation"
npm run cf:typecheck

log "Running Cloudflare deployment dry run"
npx wrangler deploy --dry-run

log "Writing final machine-readable release record"
mkdir -p "$(dirname "$FINAL_REPORT")"

python3 - \
  "$EVALUATION_REPORT" \
  "$FINAL_REPORT" \
  "$REPO_ROOT" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

evaluation_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
repo_root = Path(sys.argv[3])

evaluation = json.loads(
    evaluation_path.read_text(encoding="utf-8")
)

commit_sha = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=repo_root,
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()

branch = subprocess.run(
    ["git", "branch", "--show-current"],
    cwd=repo_root,
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()

status_lines = subprocess.run(
    ["git", "status", "--short", "--untracked-files=all"],
    cwd=repo_root,
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()

allowed_paths = {
    "README.md",
    "docs/release/PRODUCTION_RELEASE_RUNBOOK.md",
    "docs/release/QUALITY_HARDENING_FREEZE.md",
    "docs/release/QUALITY_HARDENING_RELEASE.md",
    "scripts/final-release-gate.sh",
    "apps/api/tests/evaluation/test_final_release_contract.py",
    "apps/api/artifacts/evaluation/quality-evaluation.json",
    "apps/api/artifacts/release/final-release-gate.json",
    "package.json",
}

unexpected_paths: list[str] = []

for line in status_lines:
    path_text = line[3:]

    if " -> " in path_text:
        path_text = path_text.split(" -> ", 1)[1]

    if (
        path_text not in allowed_paths
        and not path_text.startswith("docs/release/")
    ):
        unexpected_paths.append(path_text)

release_passed = (
    evaluation["release_gate"]["passed"] is True
    and not unexpected_paths
)

record = {
    "schema_version": "humanize-final-release-v1",
    "generated_at": datetime.now(UTC).isoformat(),
    "release_name": "quality-hardening-increment-8",
    "branch": branch,
    "commit_sha": commit_sha,
    "evaluation_schema_version": (
        evaluation["schema_version"]
    ),
    "evaluation_release_gate": (
        evaluation["release_gate"]
    ),
    "performance_summary": (
        evaluation["performance_summary"]
    ),
    "safety_control_gate": (
        evaluation["safety_control_gate"]
    ),
    "checks": {
        "ruff": "passed",
        "mypy": "passed",
        "pytest": "passed",
        "evaluation": "passed",
        "frontend_build": "passed",
        "cloudflare_typecheck": "passed",
        "cloudflare_dry_run": "passed",
    },
    "working_tree": {
        "status_lines": status_lines,
        "unexpected_paths": unexpected_paths,
    },
    "release_gate": {
        "passed": release_passed,
        "failures": (
            []
            if release_passed
            else [
                "Unexpected working-tree paths are present."
            ]
        ),
    },
}

output_path.write_text(
    json.dumps(
        record,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

if unexpected_paths:
    raise SystemExit(
        "Unexpected working-tree paths: "
        + ", ".join(unexpected_paths)
    )

print(f"Final release record: {output_path}")
PY

printf '\nFINAL RELEASE GATE: PASS\n'
