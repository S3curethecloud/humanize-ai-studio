from __future__ import annotations

import argparse
from pathlib import Path

from app.evaluation.report_generator import (
    write_evaluation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Generate the deterministic Humanize AI quality evaluation report."),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/quality-evaluation.json"),
        help=("Destination for the machine-readable evaluation report."),
    )
    arguments = parser.parse_args()

    report = write_evaluation_report(
        arguments.output,
    )

    release_gate = report.get("release_gate")

    if not isinstance(
        release_gate,
        dict,
    ):
        raise RuntimeError("Evaluation release gate is invalid.")

    passed = release_gate.get("passed")

    if not isinstance(
        passed,
        bool,
    ):
        raise RuntimeError("Evaluation release-gate result is invalid.")

    print(f"Evaluation report: {arguments.output}")
    print("Release gate: " + ("PASS" if passed else "FAIL"))

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
