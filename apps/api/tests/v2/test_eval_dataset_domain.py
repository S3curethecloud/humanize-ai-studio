from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.models import (
    DocumentType,
    RewriteIntensity,
)
from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationCaseReference,
    EvaluationDataset,
    EvaluationDatasetCase,
    EvaluationReferenceKind,
)
from app.v2.domain.eval_ops import (
    EVAL_OPS_VERSION,
    EvaluationDatasetIdentity,
)


def _identity(
    *,
    dataset_id: str = "rewrite-quality",
    dataset_version: str = "2026-08-16",
) -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
    )


def _input(
    *,
    text: str = "Furthermore, the launch was on May 3.",
) -> EvaluationCaseInput:
    return EvaluationCaseInput(
        text=text,
        document_type=DocumentType.TECHNICAL_DOCUMENT,
        audience="engineering leaders",
        tone="direct",
        intensity=RewriteIntensity.NATURAL_REWRITE,
        preserve_numbers=True,
        preserve_dates=True,
    )


def _reference(
    *,
    reference_id: str,
    kind: EvaluationReferenceKind,
    value: str,
) -> EvaluationCaseReference:
    return EvaluationCaseReference(
        reference_id=reference_id,
        kind=kind,
        value=value,
    )


def _case(
    *,
    case_id: str = "case-001",
    references: tuple[
        EvaluationCaseReference,
        ...,
    ] = (),
) -> EvaluationDatasetCase:
    return EvaluationDatasetCase(
        case_id=case_id,
        input=_input(),
        references=references,
    )


def test_case_input_uses_eval_ops_version() -> None:
    value = _input()

    assert value.eval_version == EVAL_OPS_VERSION


def test_case_input_preserves_rewrite_controls() -> None:
    value = _input()

    assert (
        value.document_type
        is DocumentType.TECHNICAL_DOCUMENT
    )
    assert value.audience == "engineering leaders"
    assert value.tone == "direct"
    assert (
        value.intensity
        is RewriteIntensity.NATURAL_REWRITE
    )
    assert value.preserve_numbers is True
    assert value.preserve_dates is True


def test_case_input_uses_rewrite_defaults() -> None:
    value = EvaluationCaseInput(
        text="Source."
    )

    assert value.document_type is DocumentType.GENERAL
    assert value.audience == "general audience"
    assert value.tone == "natural and clear"
    assert (
        value.intensity
        is RewriteIntensity.NATURAL_REWRITE
    )
    assert value.preserve_numbers is True
    assert value.preserve_dates is True


@pytest.mark.parametrize(
    "text",
    [
        "",
    ],
)
def test_case_input_rejects_empty_text(
    text: str,
) -> None:
    with pytest.raises(ValidationError):
        EvaluationCaseInput(
            text=text
        )


def test_case_input_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationCaseInput(
            text="Source.",
            unsupported=True,
        )


def test_case_input_is_frozen() -> None:
    value = _input()

    with pytest.raises(ValidationError):
        value.text = "Changed."


@pytest.mark.parametrize(
    "kind",
    list(EvaluationReferenceKind),
)
def test_reference_supports_declared_kinds(
    kind: EvaluationReferenceKind,
) -> None:
    reference = _reference(
        reference_id=f"reference-{kind.value}",
        kind=kind,
        value="Evidence.",
    )

    assert reference.kind is kind


def test_reference_uses_eval_ops_version() -> None:
    reference = _reference(
        reference_id="claim-1",
        kind=EvaluationReferenceKind.REQUIRED_CLAIM,
        value="The launch was on May 3.",
    )

    assert reference.eval_version == EVAL_OPS_VERSION


def test_reference_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        _reference(
            reference_id="claim-1",
            kind=EvaluationReferenceKind.REQUIRED_CLAIM,
            value="",
        )


def test_reference_is_frozen() -> None:
    reference = _reference(
        reference_id="claim-1",
        kind=EvaluationReferenceKind.REQUIRED_CLAIM,
        value="Claim.",
    )

    with pytest.raises(ValidationError):
        reference.value = "Changed."


def test_case_allows_zero_references() -> None:
    case = _case()

    assert case.references == ()


def test_case_allows_required_forbidden_and_reference_rewrite() -> None:
    references = (
        _reference(
            reference_id="required-1",
            kind=EvaluationReferenceKind.REQUIRED_CLAIM,
            value="The launch was on May 3.",
        ),
        _reference(
            reference_id="forbidden-1",
            kind=EvaluationReferenceKind.FORBIDDEN_CLAIM,
            value="The launch was delayed.",
        ),
        _reference(
            reference_id="rewrite-1",
            kind=EvaluationReferenceKind.REFERENCE_REWRITE,
            value="The launch was on May 3.",
        ),
    )

    case = _case(
        references=references
    )

    assert case.references == references


def test_case_rejects_duplicate_reference_ids() -> None:
    references = (
        _reference(
            reference_id="duplicate",
            kind=EvaluationReferenceKind.REQUIRED_CLAIM,
            value="Claim A.",
        ),
        _reference(
            reference_id="duplicate",
            kind=EvaluationReferenceKind.FORBIDDEN_CLAIM,
            value="Claim B.",
        ),
    )

    with pytest.raises(
        ValidationError,
        match="reference IDs must be unique",
    ):
        _case(
            references=references
        )


def test_case_rejects_multiple_reference_rewrites() -> None:
    references = (
        _reference(
            reference_id="rewrite-1",
            kind=EvaluationReferenceKind.REFERENCE_REWRITE,
            value="Rewrite one.",
        ),
        _reference(
            reference_id="rewrite-2",
            kind=EvaluationReferenceKind.REFERENCE_REWRITE,
            value="Rewrite two.",
        ),
    )

    with pytest.raises(
        ValidationError,
        match="at most one reference rewrite",
    ):
        _case(
            references=references
        )


@pytest.mark.parametrize(
    "kind",
    [
        EvaluationReferenceKind.REQUIRED_CLAIM,
        EvaluationReferenceKind.FORBIDDEN_CLAIM,
    ],
)
def test_case_rejects_duplicate_claim_value_within_kind(
    kind: EvaluationReferenceKind,
) -> None:
    references = (
        _reference(
            reference_id="claim-1",
            kind=kind,
            value="Same claim.",
        ),
        _reference(
            reference_id="claim-2",
            kind=kind,
            value="Same claim.",
        ),
    )

    with pytest.raises(
        ValidationError,
        match="claim references must be unique",
    ):
        _case(
            references=references
        )


def test_case_claim_duplicate_check_normalizes_outer_whitespace() -> None:
    references = (
        _reference(
            reference_id="claim-1",
            kind=EvaluationReferenceKind.REQUIRED_CLAIM,
            value="Same claim.",
        ),
        _reference(
            reference_id="claim-2",
            kind=EvaluationReferenceKind.REQUIRED_CLAIM,
            value="  Same claim.  ",
        ),
    )

    with pytest.raises(
        ValidationError,
        match="claim references must be unique",
    ):
        _case(
            references=references
        )


def test_case_rejects_claim_required_and_forbidden_simultaneously() -> None:
    references = (
        _reference(
            reference_id="required-1",
            kind=EvaluationReferenceKind.REQUIRED_CLAIM,
            value="The launch was on May 3.",
        ),
        _reference(
            reference_id="forbidden-1",
            kind=EvaluationReferenceKind.FORBIDDEN_CLAIM,
            value="The launch was on May 3.",
        ),
    )

    with pytest.raises(
        ValidationError,
        match="cannot require and forbid the same claim",
    ):
        _case(
            references=references
        )


def test_case_is_frozen() -> None:
    case = _case()

    with pytest.raises(ValidationError):
        case.case_id = "changed"


def test_dataset_uses_existing_identity_authority() -> None:
    identity = _identity()
    dataset = EvaluationDataset(
        identity=identity,
        cases=(
            _case(),
        ),
    )

    assert dataset.identity is identity
    assert dataset.eval_version == EVAL_OPS_VERSION


def test_dataset_requires_at_least_one_case() -> None:
    with pytest.raises(ValidationError):
        EvaluationDataset(
            identity=_identity(),
            cases=(),
        )


def test_dataset_preserves_case_order() -> None:
    first = _case(
        case_id="case-001"
    )
    second = _case(
        case_id="case-002"
    )

    dataset = EvaluationDataset(
        identity=_identity(),
        cases=(
            first,
            second,
        ),
    )

    assert dataset.cases == (
        first,
        second,
    )


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="case IDs must be unique",
    ):
        EvaluationDataset(
            identity=_identity(),
            cases=(
                _case(
                    case_id="duplicate"
                ),
                _case(
                    case_id="duplicate"
                ),
            ),
        )


def test_dataset_is_frozen() -> None:
    dataset = EvaluationDataset(
        identity=_identity(),
        cases=(
            _case(),
        ),
    )

    with pytest.raises(ValidationError):
        dataset.cases = ()


def test_domain_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationDatasetCase(
            case_id="case-001",
            input=_input(),
            references=(),
            unexpected="value",
        )

    with pytest.raises(ValidationError):
        EvaluationDataset(
            identity=_identity(),
            cases=(
                _case(),
            ),
            unexpected="value",
        )
