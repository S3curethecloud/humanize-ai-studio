from contextlib import contextmanager
from datetime import (
    UTC,
    datetime,
)
from types import SimpleNamespace

import pytest

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingOperationKind,
    EnterpriseProviderRoutingOperationStatus,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
    RoutingPolicy,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.enterprise_provider_routing_operation_coordinator import (
    ENTERPRISE_ROUTING_OPERATION_MISSING_SUCCESS_TERMINALIZATION_FAILURE_CODE,
    ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE,
    EnterpriseProviderRoutingOperationCoordinator,
    EnterpriseProviderRoutingOperationCoordinatorIntegrityError,
)
from app.v2.services.enterprise_provider_routing_operation_service import (
    EnterpriseProviderRoutingOperationService,
)


NOW = datetime(
    2026,
    9,
    2,
    21,
    0,
    tzinfo=UTC,
)


class _PolicyRuntime:
    def __init__(
        self,
        *,
        active: bool,
    ) -> None:
        self.active = active
        self.calls: list[
            tuple[str, str]
        ] = []

    def resolve(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ):
        self.calls.append(
            (
                workspace_id,
                user_id,
            )
        )

        if not self.active:
            return None

        return SimpleNamespace(
            workspace_id=workspace_id,
            policy_id="routing-policy-1",
            policy_revision=9,
            execution_policy=RoutingPolicy(
                policy_id="routing-policy-1",
                ordered_target_ids=(
                    "target-1",
                ),
            ),
        )


class _Provider:
    def __init__(
        self,
    ) -> None:
        self.entered = []
        self.active_context = None

    @contextmanager
    def use_routing_context(
        self,
        context,
    ):
        previous = self.active_context

        self.active_context = context
        self.entered.append(
            context
        )

        try:
            yield
        finally:
            self.active_context = previous


def _build(
    *,
    active: bool = True,
):
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    operations = (
        EnterpriseProviderRoutingOperationService(
            repository=repository,
            operation_id_factory=(
                lambda: "routing-operation-1"
            ),
            clock=(
                lambda: NOW
            ),
        )
    )

    policy_runtime = _PolicyRuntime(
        active=active
    )

    provider = _Provider()

    coordinator = (
        EnterpriseProviderRoutingOperationCoordinator(
            policy_runtime=policy_runtime,
            operations=operations,
            operation_repository=repository,
            provider=provider,
        )
    )

    return (
        coordinator,
        operations,
        repository,
        policy_runtime,
        provider,
    )


def _single_capabilities(
) -> frozenset[
    ProviderCapability
]:
    return frozenset(
        {
            ProviderCapability.REWRITE,
        }
    )


def test_inactive_policy_yields_no_operation_or_provider_context() -> None:
    (
        coordinator,
        _operations,
        repository,
        policy_runtime,
        provider,
    ) = _build(
        active=False
    )

    with coordinator.use_routing_operation(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
        ),
        required_capabilities=(
            _single_capabilities()
        ),
    ) as scope:
        assert scope is None
        assert provider.active_context is None

    assert (
        repository.get(
            "routing-operation-1"
        )
        is None
    )

    assert policy_runtime.calls == [
        (
            "workspace-1",
            "editor-1",
        )
    ]

    assert provider.entered == []


def test_active_scope_binds_context_and_completes_no_provider_execution() -> None:
    (
        coordinator,
        _operations,
        repository,
        _policy_runtime,
        provider,
    ) = _build()

    with coordinator.use_routing_operation(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
        ),
        required_capabilities=(
            _single_capabilities()
        ),
    ) as scope:
        assert scope is not None

        assert (
            provider.active_context
            is not None
        )

        assert (
            provider.active_context.operation_id
            == scope.operation_id
        )

        assert (
            provider.active_context.required_capabilities
            == _single_capabilities()
        )

        completed = coordinator.complete_success(
            scope=scope,
            rewrite_history_id="history-1",
        )

        assert (
            completed.status
            is EnterpriseProviderRoutingOperationStatus.NO_PROVIDER_EXECUTION
        )

    assert provider.active_context is None

    persisted = repository.get(
        "routing-operation-1"
    )

    assert persisted == completed


def test_success_derives_provider_execution_from_durable_bindings() -> None:
    (
        coordinator,
        operations,
        repository,
        _policy_runtime,
        _provider,
    ) = _build()

    with coordinator.use_routing_operation(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
        ),
        required_capabilities=(
            _single_capabilities()
        ),
    ) as scope:
        assert scope is not None

        operations.reserve_routing_evidence(
            operation_id=scope.operation_id,
            evidence_id="routing-evidence-1",
        )

        operations.confirm_routing_evidence(
            operation_id=scope.operation_id,
            evidence_id="routing-evidence-1",
        )

        completed = coordinator.complete_success(
            scope=scope,
            rewrite_history_id="history-1",
        )

        assert (
            completed.status
            is EnterpriseProviderRoutingOperationStatus.SUCCEEDED
        )

    persisted = repository.get(
        "routing-operation-1"
    )

    assert persisted is not None

    assert len(
        persisted.routing_evidence_bindings
    ) == 1


def test_body_failure_terminalizes_operation_and_reraises() -> None:
    (
        coordinator,
        _operations,
        repository,
        _policy_runtime,
        provider,
    ) = _build()

    with pytest.raises(
        ValueError,
        match="workspace failure",
    ):
        with coordinator.use_routing_operation(
            workspace_id="workspace-1",
            user_id="editor-1",
            operation_kind=(
                EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
            ),
            required_capabilities=(
                _single_capabilities()
            ),
        ) as scope:
            assert scope is not None
            raise ValueError(
                "workspace failure"
            )

    persisted = repository.get(
        "routing-operation-1"
    )

    assert persisted is not None

    assert (
        persisted.status
        is EnterpriseProviderRoutingOperationStatus.FAILED
    )

    assert (
        persisted.failure_code
        == ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE
    )

    assert provider.active_context is None


def test_normal_exit_without_success_terminalization_fails_closed() -> None:
    (
        coordinator,
        _operations,
        repository,
        _policy_runtime,
        _provider,
    ) = _build()

    with pytest.raises(
        EnterpriseProviderRoutingOperationCoordinatorIntegrityError,
        match="without success terminalization",
    ):
        with coordinator.use_routing_operation(
            workspace_id="workspace-1",
            user_id="editor-1",
            operation_kind=(
                EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
            ),
            required_capabilities=(
                _single_capabilities()
            ),
        ) as scope:
            assert scope is not None

    persisted = repository.get(
        "routing-operation-1"
    )

    assert persisted is not None

    assert (
        persisted.status
        is EnterpriseProviderRoutingOperationStatus.FAILED
    )

    assert (
        persisted.failure_code
        == (
            ENTERPRISE_ROUTING_OPERATION_MISSING_SUCCESS_TERMINALIZATION_FAILURE_CODE
        )
    )


def test_long_document_success_links_audit_without_caller_execution_flag() -> None:
    (
        coordinator,
        _operations,
        repository,
        _policy_runtime,
        _provider,
    ) = _build()

    capabilities = frozenset(
        {
            ProviderCapability.REWRITE,
            ProviderCapability.LONG_DOCUMENT,
        }
    )

    with coordinator.use_routing_operation(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind.LONG_DOCUMENT_REWRITE
        ),
        required_capabilities=capabilities,
    ) as scope:
        assert scope is not None

        completed = coordinator.complete_success(
            scope=scope,
            long_document_audit_id="audit-1",
        )

        assert (
            completed.status
            is EnterpriseProviderRoutingOperationStatus.NO_PROVIDER_EXECUTION
        )

        assert (
            completed.long_document_audit_id
            == "audit-1"
        )

    persisted = repository.get(
        "routing-operation-1"
    )

    assert persisted == completed
