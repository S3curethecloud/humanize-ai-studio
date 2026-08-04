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


def test_personal_ownership_accepts_personally_handled() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.PERSONAL_OWNERSHIP,
        description="Preserve direct personal ownership.",
        concept_groups=[
            ["security design"],
            ["identity"],
            ["policy"],
            ["audit boundaries"],
        ],
    )

    assert evaluate(
        source=(
            "I personally handled the security design, "
            "including identity, policy, and audit boundaries."
        ),
        rewrite=(
            "I personally handled the security design, "
            "defining the identity, policy, and audit boundaries."
        ),
        assertion=assertion,
    )


def test_personal_ownership_accepts_myself_marker() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.PERSONAL_OWNERSHIP,
        description="Preserve direct personal ownership.",
        concept_groups=[
            ["security design"],
            ["identity"],
            ["policy"],
            ["audit boundaries"],
        ],
    )

    assert evaluate(
        source=(
            "I personally handled the security design, "
            "including identity, policy, and audit boundaries."
        ),
        rewrite=(
            "I handled the security design myself, defining "
            "the identity, policy, and audit boundaries."
        ),
        assertion=assertion,
    )


def test_personal_ownership_rejects_team_only_ownership() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.PERSONAL_OWNERSHIP,
        description="Preserve direct personal ownership.",
        concept_groups=[
            ["security design"],
            ["identity"],
            ["policy"],
            ["audit boundaries"],
        ],
    )

    assert not evaluate(
        source=(
            "I personally handled the security design, "
            "including identity, policy, and audit boundaries."
        ),
        rewrite=(
            "The team handled the security design, defining "
            "the identity, policy, and audit boundaries."
        ),
        assertion=assertion,
    )


def test_concept_matching_ignores_articles() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve model and verifier responsibilities.",
        concept_groups=[
            ["the model proposes"],
            ["the verifier decides"],
        ],
    )

    assert evaluate(
        source="The model proposes; the verifier decides.",
        rewrite="Model proposes, verifier decides.",
        assertion=assertion,
    )


def test_concept_matching_accepts_finish_for_complete() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve review completion.",
        concept_groups=[
            [
                "complete the review",
                "finish the review",
                "finalize the review",
            ]
        ],
    )

    assert evaluate(
        source="Please respond so we can complete the review.",
        rewrite="Please respond so we can finish the review.",
        assertion=assertion,
    )


def test_concept_matching_accepts_handles_workflow_state() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve workflow-state responsibility.",
        concept_groups=[
            [
                "manages workflow state",
                "handles workflow state",
                "maintains workflow state",
            ]
        ],
    )

    assert evaluate(
        source="The orchestrator manages workflow state.",
        rewrite="The orchestrator handles workflow state.",
        assertion=assertion,
    )


def test_concept_matching_accepts_matters_as_importance() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve importance of secure AI architecture.",
        concept_groups=[
            ["secure AI architecture"],
            [
                "important",
                "essential",
                "critical",
                "necessary",
                "matters",
                "matters more than ever",
            ],
        ],
    )

    assert evaluate(
        source="Secure AI architecture is increasingly important.",
        rewrite="Secure AI architecture matters more than ever.",
        assertion=assertion,
    )


def test_concept_matching_accepts_importance_noun_construction() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve importance of secure AI architecture.",
        concept_groups=[
            [
                "secure AI architecture",
                "AI architecture is secure",
            ],
            [
                "important",
                "importance",
                "essential",
                "critical",
                "has never been greater",
            ],
        ],
    )

    assert evaluate(
        source="Secure AI architecture is increasingly important.",
        rewrite=("The importance of secure AI architecture has never been greater."),
        assertion=assertion,
    )


def test_concept_matching_accepts_customer_empathy_paraphrase() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve empathy and account-problem context.",
        concept_groups=[
            ["sorry", "apologize", "apologies"],
            ["trouble", "issue", "problem", "difficulty"],
            ["account"],
        ],
    )

    assert evaluate(
        source="We are sorry about the issue with your account.",
        rewrite=("We’re truly sorry for the trouble you’ve encountered with your account."),
        assertion=assertion,
    )


def test_concept_matching_accepts_inconvenience() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve the customer problem concept.",
        concept_groups=[
            [
                "trouble",
                "issue",
                "problem",
                "difficulty",
                "inconvenience",
            ]
        ],
    )

    assert evaluate(
        source="We apologize for the issue with your account.",
        rewrite=("We apologize for the inconvenience you experienced with your account."),
        assertion=assertion,
    )


def test_requirement_accepts_may_not_be_exceeded() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.REQUIREMENT,
        description="Preserve mandatory budget ceiling.",
        concept_groups=[
            ["pilot budget"],
            ["steering committee approval"],
        ],
    )

    assert evaluate(
        source=("The pilot budget must not be exceeded without steering committee approval."),
        rewrite=("The pilot budget may not be exceeded without steering committee approval."),
        assertion=assertion,
    )


def test_concept_matching_accepts_workflow_demands() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve workflow authority boundary.",
        concept_groups=[
            ["needs", "requires", "demands", "calls for"],
        ],
    )

    assert evaluate(
        source="Use only the authority the workflow requires.",
        rewrite="Use only the authority the workflow demands.",
        assertion=assertion,
    )


def test_concept_matching_accepts_initiates_tracing() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve trace creation.",
        concept_groups=[
            [
                "creates the trace",
                "initiates the trace",
                "starts the trace",
                "initiates tracing",
                "starts tracing",
            ]
        ],
    )

    assert evaluate(
        source="The gateway creates the trace.",
        rewrite="The gateway initiates tracing.",
        assertion=assertion,
    )


def test_concept_matching_accepts_human_intervention() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve human escalation when automation is unsafe.",
        concept_groups=[
            ["human escalation", "human intervention", "escalates to humans"],
            [
                "automated execution is unsafe",
                "automation is unsafe",
            ],
        ],
    )

    assert evaluate(
        source=("The platform provides human escalation when automated execution is unsafe."),
        rewrite=("The platform uses human intervention when automated execution is unsafe."),
        assertion=assertion,
    )


def test_personal_ownership_accepts_responsible_for_designing() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.PERSONAL_OWNERSHIP,
        description="Preserve direct control-plane ownership.",
        concept_groups=[
            ["control plane"],
            ["user interface", "UI"],
            ["deployment automation"],
        ],
    )

    assert evaluate(
        source=(
            "I personally designed the control plane while "
            "the team handled the UI and deployment automation."
        ),
        rewrite=(
            "I was responsible for designing the control plane, "
            "while the rest of the team focused on the user "
            "interface and deployment automation."
        ),
        assertion=assertion,
    )


def test_concept_matching_accepts_traceability_evidence() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve trace-evidence capability.",
        concept_groups=[
            [
                "trace evidence",
                "traceability evidence",
                "tracing evidence",
            ]
        ],
    )

    assert evaluate(
        source="The platform provides trace evidence.",
        rewrite="The platform offers traceability evidence.",
        assertion=assertion,
    )


def test_concept_matching_accepts_unsafe_automated_actions() -> None:
    assertion = RiskAssertion(
        assertion_type=RiskAssertionType.CONCEPT_GROUPS,
        description="Preserve unsafe-automation boundary.",
        concept_groups=[
            [
                "automated execution is unsafe",
                "automation is unsafe",
                "automated actions deemed unsafe",
                "automated actions are unsafe",
            ]
        ],
    )

    assert evaluate(
        source=("The platform escalates when automated execution is unsafe."),
        rewrite=("The platform escalates automated actions deemed unsafe."),
        assertion=assertion,
    )
