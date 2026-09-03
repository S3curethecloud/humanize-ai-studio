from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from app.core.settings import (
    ProviderName,
    Settings,
)
from app.domain.models import (
    DocumentType,
    RewriteIntensity,
    RewriteRequest,
)
from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingEvidenceBinding,
    EnterpriseProviderRoutingEvidenceBindingStatus,
    EnterpriseWorkspaceProviderRoutingOperation,
)
from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceRecord,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)
from app.v2.services.routing_eval_evidence_query_service import (
    RoutingEvidenceNotFoundError,
    RoutingEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)
from app.v2.services.workspace_provider_routing_execution_evidence_query_service import (
    WorkspaceProviderRoutingExecutionEvidenceIntegrityError,
    WorkspaceProviderRoutingExecutionEvidenceQueryService,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


TARGET_ID = "deterministic-primary"

BYPASS_TEXT = (
    "The gateway validates identity context and "
    "creates an audit trace."
)


def _binding(
    *,
    evidence_id: str,
    status: EnterpriseProviderRoutingEvidenceBindingStatus,
) -> EnterpriseProviderRoutingEvidenceBinding:
    return cast(
        EnterpriseProviderRoutingEvidenceBinding,
        SimpleNamespace(
            ordinal=1,
            evidence_id=evidence_id,
            status=status,
        ),
    )


def _operation(
    *,
    workspace_id: str = "workspace-a",
    policy_id: str = "policy-a",
    bindings: tuple[
        EnterpriseProviderRoutingEvidenceBinding,
        ...,
    ] = (),
) -> EnterpriseWorkspaceProviderRoutingOperation:
    return cast(
        EnterpriseWorkspaceProviderRoutingOperation,
        SimpleNamespace(
            operation_id="operation-a",
            workspace_id=workspace_id,
            user_id="user-a",
            policy_id=policy_id,
            routing_evidence_bindings=bindings,
        ),
    )


def _evidence(
    *,
    policy_id: str,
) -> RoutingEvidenceRecord:
    return cast(
        RoutingEvidenceRecord,
        SimpleNamespace(
            policy=SimpleNamespace(
                policy_id=policy_id,
            ),
        ),
    )


def _unit_service():
    operations = MagicMock(
        spec=(
            EnterpriseWorkspaceProviderRoutingOperationRepository
        ),
    )

    routing_evidence = MagicMock(
        spec=RoutingEvidenceQueryService,
    )

    authorization = MagicMock(
        spec=WorkspaceAuthorizationGate,
    )

    service = (
        WorkspaceProviderRoutingExecutionEvidenceQueryService(
            operations=operations,
            routing_evidence=routing_evidence,
            authorization_gate=authorization,
        )
    )

    return (
        service,
        operations,
        routing_evidence,
        authorization,
    )


def test_workspace_list_requires_audit_read_before_returning_operations() -> None:
    (
        service,
        operations,
        routing_evidence,
        authorization,
    ) = _unit_service()

    operation = _operation()

    operations.list_for_workspace.return_value = (
        operation,
    )

    result = service.list_workspace(
        workspace_id="workspace-a",
        user_id="user-a",
        limit=25,
    )

    authorization.require.assert_called_once_with(
        workspace_id="workspace-a",
        user_id="user-a",
        permission=EnterprisePermission.AUDIT_READ,
    )

    operations.list_for_workspace.assert_called_once_with(
        workspace_id="workspace-a",
        limit=25,
    )

    assert len(result) == 1
    assert result[0].operation is operation
    assert result[0].bindings == ()

    routing_evidence.get.assert_not_called()


def test_denied_workspace_read_stops_before_repository_access() -> None:
    (
        service,
        operations,
        routing_evidence,
        authorization,
    ) = _unit_service()

    authorization.require.side_effect = PermissionError(
        "membership_not_found"
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        service.list_workspace(
            workspace_id="workspace-b",
            user_id="user-a",
        )

    operations.list_for_workspace.assert_not_called()
    routing_evidence.get.assert_not_called()


def test_get_does_not_disclose_foreign_workspace_operation() -> None:
    (
        service,
        operations,
        routing_evidence,
        authorization,
    ) = _unit_service()

    foreign = _operation(
        workspace_id="workspace-b",
    )

    operations.get.return_value = foreign

    assert (
        service.get(
            workspace_id="workspace-a",
            user_id="user-a",
            operation_id="operation-a",
        )
        is None
    )

    authorization.require.assert_called_once_with(
        workspace_id="workspace-a",
        user_id="user-a",
        permission=EnterprisePermission.AUDIT_READ,
    )

    routing_evidence.get.assert_not_called()


def test_reserved_binding_remains_unresolved_without_platform_evidence_lookup() -> None:
    (
        service,
        operations,
        routing_evidence,
        _authorization,
    ) = _unit_service()

    binding = _binding(
        evidence_id="routing-evidence-reserved",
        status=(
            EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
        ),
    )

    operation = _operation(
        bindings=(
            binding,
        ),
    )

    operations.get.return_value = operation

    result = service.get(
        workspace_id="workspace-a",
        user_id="user-a",
        operation_id="operation-a",
    )

    assert result is not None
    assert len(result.bindings) == 1

    resolved = result.bindings[0]

    assert resolved.binding is binding
    assert resolved.routing_evidence is None

    routing_evidence.get.assert_not_called()


def test_recorded_binding_resolves_linked_platform_evidence() -> None:
    (
        service,
        operations,
        routing_evidence,
        _authorization,
    ) = _unit_service()

    binding = _binding(
        evidence_id="routing-evidence-recorded",
        status=(
            EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
        ),
    )

    operation = _operation(
        policy_id="policy-a",
        bindings=(
            binding,
        ),
    )

    evidence = _evidence(
        policy_id="policy-a",
    )

    operations.get.return_value = operation
    routing_evidence.get.return_value = evidence

    result = service.get(
        workspace_id="workspace-a",
        user_id="user-a",
        operation_id="operation-a",
    )

    assert result is not None
    assert len(result.bindings) == 1

    resolved = result.bindings[0]

    assert resolved.binding is binding
    assert resolved.routing_evidence is evidence

    routing_evidence.get.assert_called_once_with(
        evidence_id="routing-evidence-recorded",
    )


def test_recorded_binding_missing_platform_evidence_fails_closed() -> None:
    (
        service,
        operations,
        routing_evidence,
        _authorization,
    ) = _unit_service()

    binding = _binding(
        evidence_id="routing-evidence-missing",
        status=(
            EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
        ),
    )

    operations.get.return_value = _operation(
        bindings=(
            binding,
        ),
    )

    routing_evidence.get.side_effect = (
        RoutingEvidenceNotFoundError(
            "routing evidence does not exist"
        )
    )

    with pytest.raises(
        WorkspaceProviderRoutingExecutionEvidenceIntegrityError,
        match=(
            "recorded workspace routing evidence "
            "binding is missing platform evidence"
        ),
    ):
        service.get(
            workspace_id="workspace-a",
            user_id="user-a",
            operation_id="operation-a",
        )


def test_recorded_binding_policy_mismatch_fails_closed() -> None:
    (
        service,
        operations,
        routing_evidence,
        _authorization,
    ) = _unit_service()

    binding = _binding(
        evidence_id="routing-evidence-mismatch",
        status=(
            EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
        ),
    )

    operations.get.return_value = _operation(
        policy_id="policy-a",
        bindings=(
            binding,
        ),
    )

    routing_evidence.get.return_value = (
        _evidence(
            policy_id="policy-b",
        )
    )

    with pytest.raises(
        WorkspaceProviderRoutingExecutionEvidenceIntegrityError,
        match=(
            "policy identity does not match "
            "enterprise operation"
        ),
    ):
        service.get(
            workspace_id="workspace-a",
            user_id="user-a",
            operation_id="operation-a",
        )


def test_workspace_repository_foreign_record_fails_closed() -> None:
    (
        service,
        operations,
        _routing_evidence,
        _authorization,
    ) = _unit_service()

    operations.list_for_workspace.return_value = (
        _operation(
            workspace_id="workspace-b",
        ),
    )

    with pytest.raises(
        WorkspaceProviderRoutingExecutionEvidenceIntegrityError,
        match=(
            "repository returned foreign workspace evidence"
        ),
    ):
        service.list_workspace(
            workspace_id="workspace-a",
            user_id="user-a",
        )


def _memory_persistence(
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _provider_settings(
) -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )


def _target_settings(
) -> ProviderTargetDeclarationSettings:
    return ProviderTargetDeclarationSettings(
        targets=(
            ProviderModelTarget(
                target_id=TARGET_ID,
                provider=ProviderIdentity(
                    provider_id=(
                        DETERMINISTIC_PROVIDER_ID
                    ),
                    display_name="Deterministic",
                ),
                model=ModelIdentity(
                    provider_id=(
                        DETERMINISTIC_PROVIDER_ID
                    ),
                    model_id=(
                        DETERMINISTIC_MODEL_ID
                    ),
                ),
                capabilities=(
                    ProviderModelCapabilities(
                        capabilities=frozenset(
                            {
                                ProviderCapability.REWRITE,
                                ProviderCapability.CLAIM_LOCK,
                            }
                        ),
                    )
                ),
                enabled=True,
            ),
        ),
    )


def _canonical_services(
    monkeypatch: pytest.MonkeyPatch,
) -> V2Services:
    monkeypatch.delenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        raising=False,
    )

    return V2Services(
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )


def _provision_workspace(
    services: V2Services,
    *,
    label: str,
) -> tuple[
    str,
    str,
]:
    user = services.workspace.create_user(
        email=(
            f"routing-r6b2-{label}@example.com"
        ),
        display_name=(
            f"Routing R6B2 {label}"
        ),
    )

    workspace = (
        services.workspace_provisioning
        .create_workspace(
            user_id=user.user_id,
            name=(
                f"Routing R6B2 {label}"
            ),
        )
    )

    return (
        user.user_id,
        workspace.workspace_id,
    )


def _create_active_policy(
    services: V2Services,
    *,
    workspace_id: str,
    user_id: str,
) -> EnterpriseWorkspaceProviderRoutingPolicy:
    repository = (
        services.enterprise_provider_routing_policies
    )

    assert repository is not None

    now = datetime.now(
        UTC
    )

    policy = (
        EnterpriseWorkspaceProviderRoutingPolicy(
            policy_id=(
                f"routing-policy-{workspace_id}"
            ),
            workspace_id=workspace_id,
            status=(
                EnterpriseProviderRoutingPolicyStatus.ACTIVE
            ),
            ordered_target_ids=(
                TARGET_ID,
            ),
            fallback_policy=FallbackPolicy(),
            created_by_user_id=user_id,
            created_at=now,
            updated_by_user_id=user_id,
            updated_at=now,
            revision=1,
        )
    )

    return repository.create(
        policy
    )


def _bypass_request(
) -> RewriteRequest:
    return RewriteRequest(
        text=BYPASS_TEXT,
        document_type=DocumentType.GENERAL,
        audience="engineering leadership",
        tone="natural and clear",
        intensity=RewriteIntensity.LIGHT_EDIT,
        preserve_numbers=True,
        preserve_dates=True,
    )


def test_canonical_container_exposes_workspace_routing_execution_evidence_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _canonical_services(
        monkeypatch
    )

    assert isinstance(
        services.workspace_provider_routing_execution_evidence,
        WorkspaceProviderRoutingExecutionEvidenceQueryService,
    )


def test_custom_workflow_does_not_claim_workspace_routing_execution_evidence_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        raising=False,
    )

    services = V2Services(
        workflow=RewriteWorkflow(),
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )

    assert (
        services.workspace_provider_routing_execution_evidence
        is None
    )


def test_canonical_workspace_query_returns_authoritative_bypass_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _canonical_services(
        monkeypatch
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="authoritative",
        )
    )

    policy = _create_active_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    result = services.rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=_bypass_request(),
    )

    query = (
        services.workspace_provider_routing_execution_evidence
    )

    assert query is not None

    records = query.list_workspace(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.operation.workspace_id
        == workspace_id
    )

    assert (
        record.operation.policy_id
        == policy.policy_id
    )

    assert (
        record.operation.status.value
        == "no_provider_execution"
    )

    assert (
        record.operation.rewrite_history_id
        == result.history.rewrite_id
    )

    assert (
        record.operation.routing_evidence_bindings
        == ()
    )

    assert record.bindings == ()


def test_canonical_workspace_query_denies_cross_tenant_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _canonical_services(
        monkeypatch
    )

    user_a_id, workspace_a_id = (
        _provision_workspace(
            services,
            label="tenant-a",
        )
    )

    _user_b_id, workspace_b_id = (
        _provision_workspace(
            services,
            label="tenant-b",
        )
    )

    assert (
        workspace_a_id
        != workspace_b_id
    )

    query = (
        services.workspace_provider_routing_execution_evidence
    )

    assert query is not None

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        query.list_workspace(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
        )
