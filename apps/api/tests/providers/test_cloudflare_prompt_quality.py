from __future__ import annotations

from pathlib import Path

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

    assert 'prompt_version="cloudflare-humanize-v4"' in provider_source
