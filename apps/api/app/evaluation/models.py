from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import DocumentType, RewriteIntensity


class EvaluationCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)
    category: str = Field(default="general", min_length=1, max_length=100)
    risk_tags: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1, max_length=500)
    source_text: str = Field(min_length=1, max_length=20_000)
    document_type: DocumentType = DocumentType.GENERAL
    audience: str = Field(default="general audience", min_length=1, max_length=200)
    tone: str = Field(default="natural and clear", min_length=1, max_length=100)
    intensity: RewriteIntensity = RewriteIntensity.NATURAL_REWRITE
    expected_substrings: list[str] = Field(default_factory=list)
    expected_substring_groups: list[list[str]] = Field(default_factory=list)
    exact_preservation_substrings: list[str] = Field(default_factory=list)
    forbidden_substrings: list[str] = Field(default_factory=list)
    expected_factual_decision: str = "pass"
    expected_editorial_decision: str = "pass"


class EvaluationCaseResult(BaseModel):
    case_id: str
    category: str
    risk_tags: list[str]
    description: str
    accepted: bool
    trace_id: str
    provider_name: str
    model_name: str
    prompt_version: str
    factual_decision: str
    editorial_decision: str
    final_workflow_state: str
    expected_substrings_present: bool
    forbidden_substrings_absent: bool
    fallback_used: bool
    latency_ms: float = Field(ge=0.0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    rewritten_text: str
    failure_reasons: list[str]


class CategoryEvaluationSummary(BaseModel):
    total_cases: int = Field(ge=0)
    accepted_cases: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0.0, le=1.0)
    factual_pass_rate: float = Field(ge=0.0, le=1.0)
    editorial_pass_rate: float = Field(ge=0.0, le=1.0)


class EvaluationSummary(BaseModel):
    total_cases: int = Field(ge=0)
    accepted_cases: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0.0, le=1.0)
    factual_pass_rate: float = Field(ge=0.0, le=1.0)
    editorial_pass_rate: float = Field(ge=0.0, le=1.0)
    fallback_rate: float = Field(ge=0.0, le=1.0)
    average_latency_ms: float = Field(ge=0.0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_total_cost_usd: float | None = Field(default=None, ge=0.0)
    cost_per_accepted_rewrite_usd: float | None = Field(
        default=None,
        ge=0.0,
    )
    by_category: dict[str, CategoryEvaluationSummary] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    dataset_path: str
    provider_name: str
    model_name: str
    prompt_version: str
    input_cost_per_million_tokens_usd: float | None
    output_cost_per_million_tokens_usd: float | None
    summary: EvaluationSummary
    cases: list[EvaluationCaseResult]
