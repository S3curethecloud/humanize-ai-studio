from __future__ import annotations

from app.domain.models import (
    RewriteRequest,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ProtectedValueKind,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.claim_extractor import (
    ClaimSelectionPolicy,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationService,
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


def test_preparation_composes_claims_and_values() -> None:
    result = ClaimLockPreparationService().prepare(text=("Revenue was 42 million in 2025."))

    assert result.claim_lock is not None

    lock = result.claim_lock

    assert len(lock.claims) == 1

    assert [value.value for value in lock.values] == [
        "42",
        "2025",
    ]


def test_preparation_composes_explicit_terms() -> None:
    result = ClaimLockPreparationService().prepare(
        text=("Humanize AI Studio preserves meaning."),
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Humanize AI Studio",
            ),
        ),
    )

    assert result.claim_lock is not None

    assert [term.text for term in result.claim_lock.terms] == [
        "Humanize AI Studio",
    ]


def test_preparation_returns_none_for_empty_policy() -> None:
    result = ClaimLockPreparationService().prepare(text="Approved.")

    assert result.claim_lock is None
    assert result.protected_item_count == 0


def test_preparation_can_lower_claim_selection_threshold() -> None:
    result = ClaimLockPreparationService().prepare(
        text="Access denied.",
        claim_policy=ClaimSelectionPolicy(
            minimum_word_count=2,
        ),
    )

    assert result.claim_lock is not None
    assert len(result.claim_lock.claims) == 1


def test_preparation_defaults_to_strict_enforcement() -> None:
    result = ClaimLockPreparationService().prepare(text="Deployment completed successfully.")

    assert result.claim_lock is not None

    assert result.claim_lock.enforcement_mode is ClaimLockEnforcementMode.STRICT


def test_preparation_supports_audit_only_mode() -> None:
    result = ClaimLockPreparationService().prepare(
        text="Deployment completed successfully.",
        enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
    )

    assert result.claim_lock is not None

    assert result.claim_lock.enforcement_mode is ClaimLockEnforcementMode.AUDIT_ONLY


def test_lock_id_is_stable_across_runs() -> None:
    service = ClaimLockPreparationService()

    first = service.prepare(text="Revenue was 42 million.")
    second = service.prepare(text="Revenue was 42 million.")

    assert first.claim_lock is not None
    assert second.claim_lock is not None

    assert first.claim_lock.lock_id == second.claim_lock.lock_id


def test_preparation_propagates_provenance() -> None:
    result = ClaimLockPreparationService().prepare(
        text=("Policy requires human review for 42 cases."),
        origin=ClaimLockOrigin.WORKSPACE,
        source_reference="workspace-policy-11",
    )

    assert result.claim_lock is not None

    lock = result.claim_lock

    assert lock.claims[0].provenance.origin is ClaimLockOrigin.WORKSPACE
    assert lock.claims[0].provenance.source_reference == "workspace-policy-11"

    assert lock.values[0].kind is ProtectedValueKind.NUMBER
    assert lock.values[0].provenance.source_reference == "workspace-policy-11"


def test_preparation_exposes_extractor_versions() -> None:
    result = ClaimLockPreparationService().prepare(text="Revenue was 42 million.")

    assert result.preparation_version == "claim-lock-preparation-v1"
    assert result.claim_extraction.extractor_version == "claim-extractor-v1"
    assert result.protected_item_extraction.extractor_version == "claim-lock-extractor-v1"


def test_workspace_rewrite_prepares_claim_lock_and_preserves_history() -> None:
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
        workspace_service=workspace_service,
        history=history_repository,
    )

    rewrite_service = WorkspaceRewriteService(
        workspace_service=workspace_service,
        history_service=history_service,
        workflow=RewriteWorkflow(),
    )

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Claim Lock Workspace",
    )

    result = rewrite_service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=RewriteRequest(
            text=("Revenue was 42 million in 2025."),
        ),
    )

    preparation = result.claim_lock_preparation

    assert preparation.claim_lock is not None

    lock = preparation.claim_lock

    assert len(lock.claims) == 1
    assert [value.value for value in lock.values] == [
        "42",
        "2025",
    ]

    assert result.history.trace_id == result.response.trace_id

    records = history_service.list_workspace_history(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
    )

    assert records == (result.history,)
