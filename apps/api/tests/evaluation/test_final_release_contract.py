import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_package_exposes_final_release_gate() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["release:gate"] == ("bash scripts/final-release-gate.sh")


def test_final_release_gate_enforces_required_checks() -> None:
    script = (REPO_ROOT / "scripts" / "final-release-gate.sh").read_text(encoding="utf-8")

    required_commands = (
        "ruff check . --fix",
        "ruff format .",
        "mypy app tests",
        "pytest -q",
        "python3 -m app.evaluation",
        "npm run build:web",
        "npm run cf:typecheck",
        "npx wrangler deploy --dry-run",
    )

    for command in required_commands:
        assert command in script


def test_final_release_gate_checks_safety_metrics() -> None:
    script = (REPO_ROOT / "scripts" / "final-release-gate.sh").read_text(encoding="utf-8")

    assert "unsafe_output_release_count" in script
    assert "maximum_observed_model_call_count" in script
    assert "controlled_fallback_count" in script
    assert "humanize-final-release-v1" in script


def test_release_documentation_declares_code_freeze() -> None:
    release_document = (REPO_ROOT / "docs" / "release" / "QUALITY_HARDENING_RELEASE.md").read_text(
        encoding="utf-8"
    )

    freeze_document = (REPO_ROOT / "docs" / "release" / "QUALITY_HARDENING_FREEZE.md").read_text(
        encoding="utf-8"
    )

    assert "The quality-hardening program ends with Increment 8" in (release_document)
    assert "The quality-hardening freeze applies after completion of Increment 8" in (
        freeze_document
    )
