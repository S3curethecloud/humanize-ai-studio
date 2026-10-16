"""Fail-closed protected-fact conflict detection for Humanize V3.5."""

from __future__ import annotations

from collections.abc import Mapping

from app.v3.ndeb.contracts import JsonValue

from .contracts import (
    CompositionContentKind,
    CompositionInput,
    CompositionIssue,
    CompositionIssueCode,
)


def _binding_key(item: CompositionInput) -> tuple[str, str, int]:
    binding = item.source_authority_binding
    return (binding.record_type, binding.record_id, binding.record_version)


def detect_protected_fact_conflicts(
    inputs: tuple[CompositionInput, ...],
) -> tuple[CompositionIssue, ...]:
    protected = tuple(
        item
        for item in inputs
        if item.content_kind is CompositionContentKind.PROTECTED_FACT
        and item.protected_fact is not None
    )

    issues: list[CompositionIssue] = []
    seen: dict[tuple[str, str, int], CompositionInput] = {}

    for item in protected:
        key = _binding_key(item)
        previous = seen.get(key)
        if previous is None:
            seen[key] = item
            continue

        previous_fact = previous.protected_fact
        current_fact = item.protected_fact
        if previous_fact is None or current_fact is None:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.PROTECTED_FACT_CONFLICT,
                    input_id=item.input_id,
                )
            )
            continue

        exact_duplicate = (
            previous_fact.fact_id == current_fact.fact_id
            and previous.source_authority_binding
            == item.source_authority_binding
            and previous.provenance_binding == item.provenance_binding
            and previous.classification == item.classification
            and previous_fact.material == current_fact.material
        )
        if not exact_duplicate:
            issues.append(
                CompositionIssue(
                    code=CompositionIssueCode.PROTECTED_FACT_CONFLICT,
                    input_id=item.input_id,
                )
            )

    return tuple(issues)


def authoritative_classification(
    inputs: tuple[CompositionInput, ...],
) -> tuple[Mapping[str, JsonValue] | None, tuple[CompositionIssue, ...]]:
    protected = tuple(
        item
        for item in inputs
        if item.content_kind is CompositionContentKind.PROTECTED_FACT
    )
    if not protected:
        return None, ()

    classification = protected[0].classification
    for item in protected[1:]:
        if item.classification != classification:
            return (
                None,
                (
                    CompositionIssue(
                        code=CompositionIssueCode.CLASSIFICATION_CONFLICT,
                        input_id=item.input_id,
                    ),
                ),
            )
    return classification, ()
