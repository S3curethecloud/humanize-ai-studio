from __future__ import annotations

from tests.v2.test_support_authorization_gate import allow_all_workspace_authorization_gate
from app.domain.models import (
    RewriteRequest,
)
from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedClaim,
    ProtectedTerm,
    ProtectedValue,
    ProtectedValueKind,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockCheckStatus,
    ClaimLockValidationCheck,
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
    ClaimLockValidator,
    ClaimLockViolationError,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_rewrite_service import (
    WorkspaceRewriteService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _provenance() -> ClaimLockProvenance:
    return ClaimLockProvenance(
        origin=ClaimLockOrigin.REQUEST,
        source_reference="rewrite-request",
    )


def _claim_lock(
    *,
    enforcement_mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
    claims: tuple[
        ProtectedClaim,
        ...,
    ] = (),
    terms: tuple[
        ProtectedTerm,
        ...,
    ] = (),
    values: tuple[
        ProtectedValue,
        ...,
    ] = (),
) -> ClaimLock:
    return ClaimLock(
        lock_id="lock_test",
        enforcement_mode=enforcement_mode,
        claims=claims,
        terms=terms,
        values=values,
    )


def test_no_claim_lock_passes() -> None:
    result = ClaimLockValidator().validate(
        claim_lock=None,
        rewritten_text="Any rewritten text.",
    )

    assert result.decision is ClaimLockValidationDecision.PASS
    assert result.checks == ()
    assert result.lock_id is None


def test_claim_is_explicitly_not_evaluated() -> None:
    lock = _claim_lock(
        claims=(
            ProtectedClaim(
                claim_id="claim_1",
                text=("Revenue increased during the quarter."),
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("Quarterly revenue grew."),
    )

    assert result.decision is ClaimLockValidationDecision.PASS

    check = result.checks[0]

    assert check.item_type == "claim"
    assert check.status is ClaimLockCheckStatus.NOT_EVALUATED
    assert result.unevaluated_claim_ids == ("claim_1",)


def test_case_sensitive_term_is_preserved() -> None:
    lock = _claim_lock(
        terms=(
            ProtectedTerm(
                term_id="term_1",
                text="SecureTheCloud",
                case_sensitive=True,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("SecureTheCloud remains the approved platform."),
    )

    assert result.decision is ClaimLockValidationDecision.PASS
    assert result.checks[0].status is ClaimLockCheckStatus.PRESERVED


def test_case_sensitive_term_missing_on_case_change() -> None:
    lock = _claim_lock(
        terms=(
            ProtectedTerm(
                term_id="term_1",
                text="SecureTheCloud",
                case_sensitive=True,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("securethecloud remains the approved platform."),
    )

    assert result.decision is ClaimLockValidationDecision.VIOLATION
    assert result.violating_item_ids == ("term_1",)


def test_case_insensitive_term_allows_case_change() -> None:
    lock = _claim_lock(
        terms=(
            ProtectedTerm(
                term_id="term_1",
                text="Human Review",
                case_sensitive=False,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("The workflow requires HUMAN REVIEW."),
    )

    assert result.decision is ClaimLockValidationDecision.PASS


def test_protected_value_is_preserved_exactly() -> None:
    lock = _claim_lock(
        values=(
            ProtectedValue(
                value_id="value_1",
                value="$42,500.75",
                kind=ProtectedValueKind.NUMBER,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("Revenue remained $42,500.75."),
    )

    assert result.decision is ClaimLockValidationDecision.PASS


def test_protected_value_change_is_violation() -> None:
    lock = _claim_lock(
        values=(
            ProtectedValue(
                value_id="value_1",
                value="42%",
                kind=(ProtectedValueKind.PERCENTAGE),
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("Growth reached 43%."),
    )

    assert result.decision is ClaimLockValidationDecision.VIOLATION
    assert result.violating_item_ids == ("value_1",)


def test_url_is_checked_as_exact_protected_value() -> None:
    lock = _claim_lock(
        values=(
            ProtectedValue(
                value_id="value_1",
                value="https://example.com/a",
                kind=ProtectedValueKind.URL,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("See https://example.com/b."),
    )

    assert result.decision is ClaimLockValidationDecision.VIOLATION


def test_mixed_checks_violate_only_for_missing_items() -> None:
    lock = _claim_lock(
        claims=(
            ProtectedClaim(
                claim_id="claim_1",
                text=("The deployment was approved."),
                provenance=_provenance(),
            ),
        ),
        terms=(
            ProtectedTerm(
                term_id="term_1",
                text="ACME",
                provenance=_provenance(),
            ),
        ),
        values=(
            ProtectedValue(
                value_id="value_1",
                value="2026-08-11",
                kind=ProtectedValueKind.DATE,
                provenance=_provenance(),
            ),
        ),
    )

    result = ClaimLockValidator().validate(
        claim_lock=lock,
        rewritten_text=("ACME approved the deployment."),
    )

    assert result.decision is ClaimLockValidationDecision.VIOLATION
    assert result.violating_item_ids == ("value_1",)
    assert result.unevaluated_claim_ids == ("claim_1",)


class _AlwaysViolationValidator(ClaimLockValidator):
    def validate(
        self,
        *,
        claim_lock: ClaimLock | None,
        rewritten_text: str,
    ) -> ClaimLockValidationResult:
        del rewritten_text

        if claim_lock is None:
            raise AssertionError("test requires a prepared claim lock")

        item_id = (
            claim_lock.claims[0].claim_id if claim_lock.claims else claim_lock.values[0].value_id
        )

        return ClaimLockValidationResult(
            lock_id=claim_lock.lock_id,
            enforcement_mode=(claim_lock.enforcement_mode),
            decision=(ClaimLockValidationDecision.VIOLATION),
            checks=(
                ClaimLockValidationCheck(
                    item_id=item_id,
                    item_type=("claim" if claim_lock.claims else "value"),
                    expected_text="forced-test-item",
                    status=(ClaimLockCheckStatus.MISSING),
                    reason="forced test violation",
                ),
            ),
        )


def _build_workspace_rewrite_service(
    *,
    validator: ClaimLockValidator,
) -> tuple[
    WorkspaceRewriteService,
    WorkspaceService,
    RewriteHistoryService,
    str,
    str,
]:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()
    history_repository = InMemoryRewriteHistoryRepository()

    workspace_service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    history_service = RewriteHistoryService(
        history=history_repository,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    rewrite_service = WorkspaceRewriteService(
        history_service=history_service,
        workflow=RewriteWorkflow(),
        claim_lock_validator=validator,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Claim Lock Workspace",
    )

    return (
        rewrite_service,
        workspace_service,
        history_service,
        user.user_id,
        workspace.workspace_id,
    )


def test_strict_violation_fails_before_history_persistence() -> None:
    (
        rewrite_service,
        _,
        history_service,
        user_id,
        workspace_id,
    ) = _build_workspace_rewrite_service(
        validator=_AlwaysViolationValidator(),
    )

    request = RewriteRequest(text="Deployment completed successfully.")

    try:
        rewrite_service.execute(
            workspace_id=workspace_id,
            user_id=user_id,
            request=request,
        )
    except ClaimLockViolationError as exc:
        assert exc.validation.decision is ClaimLockValidationDecision.VIOLATION
    else:
        raise AssertionError("Expected ClaimLockViolationError.")

    records = history_service.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert records == ()


def test_audit_only_violation_returns_and_records_history() -> None:
    (
        rewrite_service,
        _,
        history_service,
        user_id,
        workspace_id,
    ) = _build_workspace_rewrite_service(
        validator=_AlwaysViolationValidator(),
    )

    result = rewrite_service.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=RewriteRequest(
            text=("Deployment completed successfully."),
        ),
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
    )

    assert result.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION

    assert result.claim_lock_preparation.claim_lock is not None

    assert (
        result.claim_lock_preparation.claim_lock.enforcement_mode
        is ClaimLockEnforcementMode.AUDIT_ONLY
    )

    records = history_service.list_workspace_history(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert records == (result.history,)


def test_successful_workspace_rewrite_returns_validation_evidence() -> None:
    (
        rewrite_service,
        _,
        _,
        user_id,
        workspace_id,
    ) = _build_workspace_rewrite_service(
        validator=ClaimLockValidator(),
    )

    result = rewrite_service.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=RewriteRequest(
            text=("Deployment completed successfully."),
        ),
    )

    assert result.claim_lock_validation.validator_version == "claim-lock-validator-v1"

    assert result.claim_lock_validation.decision is ClaimLockValidationDecision.PASS

    assert result.claim_lock_validation.unevaluated_claim_ids
