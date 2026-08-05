from __future__ import annotations

from pathlib import Path

from app.domain.models import RewriteRequest
from app.providers.cloudflare import CloudflareWorkersAIProvider


def test_system_prompt_prohibits_qualification_inflation() -> None:
    prompt = CloudflareWorkersAIProvider._system_prompt()

    required_rules = (
        "Never strengthen a qualification or level of experience.",
        "Never convert experience into expertise or mastery.",
        "Never convert participation into ownership or leadership.",
        "Never add an achievement, result, outcome, metric, capability",
        "Deep reconstruction authorizes structural change",
        "increases seniority, expertise, ownership, scope, certainty, or impact",
    )

    for rule in required_rules:
        assert rule in prompt


def test_system_prompt_names_known_inflation_failures() -> None:
    prompt = CloudflareWorkersAIProvider._system_prompt()

    prohibited_phrases = (
        "extensive experience",
        "developed expertise",
        "leveraging a range of technologies",
        "to drive effective solutions",
        "proven track record",
        "robust and seamless",
    )

    for phrase in prohibited_phrases:
        assert phrase in prompt


def test_system_prompt_preserves_claim_dimensions() -> None:
    prompt = CloudflareWorkersAIProvider._system_prompt()

    protected_dimensions = (
        "level of certainty",
        "level of experience",
        "ownership",
        "scope",
        "authority",
        "qualification",
        "limitation",
        "negation",
    )

    for dimension in protected_dimensions:
        assert dimension in prompt


def test_system_prompt_defines_all_rewrite_distances() -> None:
    prompt = CloudflareWorkersAIProvider._system_prompt()

    assert "light_polish:" in prompt
    assert "moderate_rewrite:" in prompt
    assert "deep_reconstruction:" in prompt


def test_prompt_version_is_incremented() -> None:
    provider_source = Path("app/providers/cloudflare.py").read_text(encoding="utf-8")

    assert 'prompt_version="cloudflare-humanize-v8"' in provider_source


def test_repair_prompt_requires_structural_deep_reconstruction() -> None:
    prompt = CloudflareWorkersAIProvider._repair_prompt(
        request=RewriteRequest(
            text=(
                "I have hands-on experience designing "
                "generative AI systems across RAG and "
                "agentic workflows."
            ),
            document_type="professional_email",
            audience="technical hiring team",
            tone="natural and professional",
            intensity="deep_reconstruction",
        ),
        rejected_text=(
            "I have developed expertise in generative AI across RAG and agentic workflows."
        ),
        violation_summary=("- qualification_removed: 'hands-on experience'"),
        required_phrases=("hands-on experience",),
    )

    assert "REQUIRED VERBATIM PHRASES" in prompt
    assert "hands-on experience" in prompt
    assert "materially reorganize sentence" in prompt
    assert "Move a clause, reorder major ideas" in prompt
    assert "narrow synonym substitution" in prompt


def test_deep_repair_blueprint_reorders_multiple_sentences() -> None:
    request = RewriteRequest(
        text=(
            "I have hands-on experience designing generative "
            "AI systems. I work across RAG and agentic workflows."
        ),
        document_type="professional_email",
        audience="technical hiring team",
        tone="natural and professional",
        intensity="deep_reconstruction",
    )

    blueprint = CloudflareWorkersAIProvider._structural_repair_blueprint(request)

    assert "final source sentence" in blueprint
    assert "Do not preserve the source sentence order" in blueprint


def test_deep_repair_blueprint_splits_single_sentence() -> None:
    request = RewriteRequest(
        text=(
            "I have hands-on experience designing generative "
            "AI systems across RAG and agentic workflows."
        ),
        document_type="professional_email",
        audience="technical hiring team",
        tone="natural and professional",
        intensity="deep_reconstruction",
    )

    blueprint = CloudflareWorkersAIProvider._structural_repair_blueprint(request)

    assert "split the source into at least two sentences" in blueprint
    assert "Do not preserve the original clause order" in blueprint


def test_repair_prompt_contains_required_structural_blueprint() -> None:
    request = RewriteRequest(
        text=(
            "I have hands-on experience designing generative "
            "AI systems. I work across RAG and agentic workflows."
        ),
        document_type="professional_email",
        audience="technical hiring team",
        tone="natural and professional",
        intensity="deep_reconstruction",
    )

    prompt = CloudflareWorkersAIProvider._repair_prompt(
        request=request,
        rejected_text=(
            "I developed expertise in generative AI systems across RAG and agentic workflows."
        ),
        violation_summary=("- qualification_removed: 'hands-on experience'"),
        required_phrases=("hands-on experience",),
    )

    assert "REQUIRED STRUCTURAL BLUEPRINT" in prompt
    assert "final source sentence" in prompt
    assert "Apply the REQUIRED STRUCTURAL BLUEPRINT visibly" in prompt
