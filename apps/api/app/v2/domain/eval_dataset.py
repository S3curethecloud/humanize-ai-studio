from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.models import (
    DocumentType,
    RewriteIntensity,
)
from app.v2.domain.eval_ops import (
    EVAL_OPS_VERSION,
    EvaluationDatasetIdentity,
)


class EvaluationReferenceKind(StrEnum):
    REQUIRED_CLAIM = "required_claim"
    FORBIDDEN_CLAIM = "forbidden_claim"
    REFERENCE_REWRITE = "reference_rewrite"


class EvaluationCaseInput(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    text: str = Field(
        min_length=1,
        max_length=20_000,
    )
    document_type: DocumentType = DocumentType.GENERAL
    audience: str = Field(
        default="general audience",
        min_length=1,
        max_length=200,
    )
    tone: str = Field(
        default="natural and clear",
        min_length=1,
        max_length=100,
    )
    intensity: RewriteIntensity = (
        RewriteIntensity.NATURAL_REWRITE
    )
    preserve_numbers: bool = True
    preserve_dates: bool = True


class EvaluationCaseReference(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    reference_id: str = Field(
        min_length=1,
        max_length=200,
    )
    kind: EvaluationReferenceKind
    value: str = Field(
        min_length=1,
        max_length=20_000,
    )


class EvaluationDatasetCase(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    case_id: str = Field(
        min_length=1,
        max_length=200,
    )
    input: EvaluationCaseInput
    references: tuple[
        EvaluationCaseReference,
        ...,
    ] = ()

    @model_validator(mode="after")
    def require_case_integrity(
        self,
    ) -> EvaluationDatasetCase:
        reference_ids = tuple(
            reference.reference_id
            for reference in self.references
        )

        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError(
                "evaluation case reference IDs must be unique"
            )

        reference_rewrites = tuple(
            reference
            for reference in self.references
            if (
                reference.kind
                is EvaluationReferenceKind.REFERENCE_REWRITE
            )
        )

        if len(reference_rewrites) > 1:
            raise ValueError(
                "evaluation case may contain at most one "
                "reference rewrite"
            )

        claim_values_by_kind: dict[
            EvaluationReferenceKind,
            set[str],
        ] = {
            EvaluationReferenceKind.REQUIRED_CLAIM: set(),
            EvaluationReferenceKind.FORBIDDEN_CLAIM: set(),
        }

        for reference in self.references:
            if reference.kind not in claim_values_by_kind:
                continue

            normalized_value = reference.value.strip()

            if normalized_value in claim_values_by_kind[
                reference.kind
            ]:
                raise ValueError(
                    "evaluation case claim references must be "
                    "unique within each reference kind"
                )

            claim_values_by_kind[
                reference.kind
            ].add(normalized_value)

        overlap = (
            claim_values_by_kind[
                EvaluationReferenceKind.REQUIRED_CLAIM
            ]
            & claim_values_by_kind[
                EvaluationReferenceKind.FORBIDDEN_CLAIM
            ]
        )

        if overlap:
            raise ValueError(
                "evaluation case cannot require and forbid "
                "the same claim"
            )

        return self


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    identity: EvaluationDatasetIdentity
    cases: tuple[
        EvaluationDatasetCase,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_dataset_integrity(
        self,
    ) -> EvaluationDataset:
        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(set(case_ids)) != len(case_ids):
            raise ValueError(
                "evaluation dataset case IDs must be unique"
            )

        return self
