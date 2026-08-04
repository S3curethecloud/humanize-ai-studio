from app.evaluation.models import (
    RiskAssertion,
    RiskAssertionType,
)
from app.evaluation.risk_assertions import RiskAssertionEvaluator


def evaluate(
    *,
    source: str,
    rewrite: str,
    assertion: RiskAssertion,
) -> bool:
    results = RiskAssertionEvaluator().evaluate(
        source_text=source,
        rewritten_text=rewrite,
        assertions=[assertion],
    )

    return results[0].passed


def test_numeric_assertion_accepts_number_word() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.NUMERIC_EQUIVALENCE,
        description="Preserve response period.",
        values=["2 business days"],
    )

    assert evaluate(
        source="We will respond within 2 business days.",
        rewrite="We will respond within two business days.",
        assertion=assertion,
    )


def test_numeric_assertion_accepts_p95_equivalence() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.NUMERIC_EQUIVALENCE,
        description="Preserve latency percentile.",
        values=["p95", "2 seconds", "$0.01"],
    )

    assert evaluate(
        source="p95 latency below 2 seconds at $0.01.",
        rewrite=("The 95th-percentile latency is under 2 seconds at less than $0.01."),
        assertion=assertion,
    )


def test_negation_assertion_preserves_negative_outcome() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.NEGATION,
        description="Deployment must remain blocked.",
        concept_groups=[
            ["deployment"],
            ["security review"],
        ],
    )

    assert evaluate(
        source=("The deployment will not begin until the security review is complete."),
        rewrite=("The deployment will not start until the security review is complete."),
        assertion=assertion,
    )


def test_prohibition_assertion_accepts_shall_not() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.PROHIBITION,
        description="Prompts must not be logged.",
        concept_groups=[
            ["raw customer prompts"],
            ["analytics", "analytics logs"],
        ],
    )

    assert evaluate(
        source=("The system must not store raw customer prompts in analytics logs."),
        rewrite=("The system shall not log raw customer prompts in analytics."),
        assertion=assertion,
    )


def test_requirement_assertion_accepts_budget_ceiling() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.REQUIREMENT,
        description="Budget ceiling remains mandatory.",
        concept_groups=[
            ["approved pilot budget", "pilot budget"],
            ["steering committee approval"],
        ],
    )

    assert evaluate(
        source=(
            "The approved pilot budget is $75,000 and must "
            "not be exceeded without steering committee approval."
        ),
        rewrite=(
            "The approved pilot budget is $75,000 and cannot "
            "be exceeded without steering committee approval."
        ),
        assertion=assertion,
    )


def test_concept_groups_accept_authority_paraphrase() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve proposal and authority boundary.",
        concept_groups=[
            ["suggest an action", "propose an action"],
            [
                "cannot authorize",
                "does not have the authority to approve",
            ],
            ["deterministic policy layer"],
            ["human approver"],
        ],
    )

    assert evaluate(
        source=("The model can propose an action but cannot authorize it."),
        rewrite=(
            "The model may suggest an action, but it does not "
            "have the authority to approve it. Authorization "
            "remains with the deterministic policy layer and "
            "a human approver."
        ),
        assertion=assertion,
    )


def test_minimal_change_rejects_unnecessary_reconstruction() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.MINIMAL_CHANGE,
        description="Already-good text should remain stable.",
        minimum_similarity=0.85,
    )

    assert not evaluate(
        source=("The policy engine evaluates every proposed tool call before execution."),
        rewrite=("Before executing any tool call, the policy engine evaluates it."),
        assertion=assertion,
    )


def test_numeric_assertion_accepts_shared_unit_range() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.NUMERIC_EQUIVALENCE,
        description="Preserve onboarding measurements.",
        values=["10 days", "3 days"],
    )

    assert evaluate(
        source=("The program reduced onboarding time from 10 days to 3 days."),
        rewrite=("The program cut onboarding time from 10 to 3 days."),
        assertion=assertion,
    )


def test_concept_matching_accepts_plural_morphology() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve action proposal.",
        concept_groups=[
            ["suggest an action", "propose an action"],
        ],
    )

    assert evaluate(
        source="The model can propose an action.",
        rewrite="The model can suggest actions.",
        assertion=assertion,
    )


def test_concept_matching_accepts_authorization_morphology() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve authorization boundary.",
        concept_groups=[
            ["grant authorization"],
        ],
    )

    assert evaluate(
        source="The model cannot authorize the action.",
        rewrite="The model does not grant authorization.",
        assertion=assertion,
    )


def test_concept_matching_accepts_escalation_morphology() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve human escalation.",
        concept_groups=[
            ["human escalation", "escalates to humans"],
        ],
    )

    assert evaluate(
        source="The workflow supports human escalation.",
        rewrite="The workflow escalates to humans when necessary.",
        assertion=assertion,
    )
