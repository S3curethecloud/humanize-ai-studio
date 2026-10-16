"""Deterministic explicit ordering for Humanize V3.5 composition."""

from __future__ import annotations

from .contracts import CompositionInput, CompositionIssue, CompositionIssueCode


def order_inputs(
    inputs: tuple[CompositionInput, ...],
) -> tuple[tuple[CompositionInput, ...], tuple[CompositionIssue, ...]]:
    issues: list[CompositionIssue] = []

    ids: set[str] = set()
    positions: set[int] = set()

    for item in inputs:
        if not isinstance(item.input_id, str) or not item.input_id.strip():
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.INVALID_INPUT,
                    input_id=None,
                )
            )
        elif item.input_id in ids:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.DUPLICATE_INPUT_ID,
                    input_id=item.input_id,
                )
            )
        else:
            ids.add(item.input_id)

        if (
            not isinstance(item.position, int)
            or isinstance(item.position, bool)
            or item.position < 0
        ):
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.INVALID_POSITION,
                    input_id=item.input_id if isinstance(item.input_id, str) else None,
                )
            )
            continue

        if item.position in positions:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.DUPLICATE_POSITION,
                    input_id=item.input_id,
                )
            )
        else:
            positions.add(item.position)

    if issues:
        return (), tuple(issues)

    return tuple(sorted(inputs, key=lambda item: item.position)), ()
