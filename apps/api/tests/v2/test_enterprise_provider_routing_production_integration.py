from pathlib import Path

from app.core.settings import (
    ProviderName,
    Settings,
)
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    ProviderTargetDeclarationSettings,
)
from app.v2.services.enterprise_provider_routing_operation_coordinator import (
    EnterpriseProviderRoutingOperationCoordinator,
)
from app.v2.services.enterprise_routing_aware_provider import (
    EnterpriseRoutingAwareRewriteProvider,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
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
    return (
        ProviderTargetDeclarationSettings
        .from_environment()
    )


def test_canonical_container_activates_shared_enterprise_routing_composition(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    services = V2Services(
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )

    coordinator = (
        services
        .enterprise_provider_routing_operation_coordinator
    )

    routing_provider = (
        services.enterprise_routing_aware_provider
    )

    assert isinstance(
        coordinator,
        EnterpriseProviderRoutingOperationCoordinator,
    )

    assert isinstance(
        routing_provider,
        EnterpriseRoutingAwareRewriteProvider,
    )

    assert (
        services.enterprise_provider_routing_policies
        is not None
    )

    assert (
        services.enterprise_provider_routing_operations
        is not None
    )

    assert (
        services.enterprise_provider_routing_policy_runtime
        is not None
    )

    assert (
        services.enterprise_provider_routing_operation_service
        is not None
    )

    assert (
        services.rewrite._routing_operation_coordinator
        is coordinator
    )

    assert (
        services.multi_candidate
        ._routing_operation_coordinator
        is coordinator
    )

    assert (
        services.long_document
        ._routing_operation_coordinator
        is coordinator
    )

    workflow_provider = (
        services.rewrite._workflow._provider
    )

    assert isinstance(
        workflow_provider,
        VoiceAwareRewriteProvider,
    )

    assert (
        workflow_provider._provider
        is routing_provider
    )

    assert (
        services.multi_candidate._voice_provider
        is workflow_provider
    )

    assert services.voice_rewrite is not None

    assert (
        services.voice_rewrite._provider
        is workflow_provider
    )


def test_custom_workflow_dependency_injection_does_not_claim_routing_activation(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PROVIDER_TARGETS_JSON",
        raising=False,
    )

    workflow = RewriteWorkflow()

    services = V2Services(
        workflow=workflow,
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
    )

    assert (
        services.enterprise_provider_routing_policies
        is None
    )

    assert (
        services.enterprise_provider_routing_operations
        is None
    )

    assert (
        services.enterprise_provider_routing_policy_runtime
        is None
    )

    assert (
        services.enterprise_provider_routing_operation_service
        is None
    )

    assert (
        services.enterprise_routing_aware_provider
        is None
    )

    assert (
        services
        .enterprise_provider_routing_operation_coordinator
        is None
    )

    assert services.rewrite._workflow is workflow

    assert (
        services.rewrite._routing_operation_coordinator
        is None
    )

    assert (
        services.multi_candidate
        ._routing_operation_coordinator
        is None
    )

    assert (
        services.long_document
        ._routing_operation_coordinator
        is None
    )


def _source(
    relative_path: str,
) -> str:
    return Path(
        relative_path
    ).read_text()


def _assert_order(
    text: str,
    *tokens: str,
) -> None:
    positions = [
        text.index(token)
        for token in tokens
    ]

    assert positions == sorted(
        positions
    )


def test_single_routing_scope_uses_frozen_capabilities_and_success_boundary() -> None:
    text = _source(
        "app/v2/services/"
        "workspace_rewrite_service.py"
    )

    assert (
        "EnterpriseProviderRoutingOperationKind."
        "SINGLE_REWRITE"
        in text
    )

    assert "ProviderCapability.REWRITE" in text
    assert "ProviderCapability.CLAIM_LOCK" in text
    assert "ProviderCapability.VOICE_PROFILE" in text

    assert (
        "rewrite_history_id=history.rewrite_id"
        in text
    )

    _assert_order(
        text,
        "with routing_operation as routing_scope:",
        "response = self._workflow.execute(request)",
        "history = self._history_service.record_rewrite(",
        "coordinator.complete_success(",
        "if self._observability is not None:",
    )


def test_multi_routing_scope_preserves_c0a_and_frozen_capabilities() -> None:
    text = _source(
        "app/v2/services/"
        "multi_candidate_rewrite_service.py"
    )

    assert (
        "legacy_claim_lock_preparation.claim_lock"
        in text
    )

    assert (
        "EnterpriseProviderRoutingOperationKind."
        "MULTI_CANDIDATE_REWRITE"
        in text
    )

    assert "ProviderCapability.REWRITE" in text
    assert "ProviderCapability.MULTI_CANDIDATE" in text
    assert "ProviderCapability.CLAIM_LOCK" in text
    assert "ProviderCapability.VOICE_PROFILE" in text

    assert (
        "rewrite_history_id=history.rewrite_id"
        in text
    )

    _assert_order(
        text,
        "legacy_claim_lock_preparation = (",
        "with routing_operation as routing_scope:",
        "controlled = self._execute_controlled(",
        "history = self._history_service.record_rewrite(",
        "coordinator.complete_success(",
        "if self._observability is not None:",
    )


def test_long_routing_scope_has_no_voice_capability_and_links_audit() -> None:
    text = _source(
        "app/v2/services/"
        "long_document_rewrite_service.py"
    )

    assert (
        "EnterpriseProviderRoutingOperationKind."
        "LONG_DOCUMENT_REWRITE"
        in text
    )

    assert "ProviderCapability.REWRITE" in text
    assert "ProviderCapability.LONG_DOCUMENT" in text
    assert "ProviderCapability.CLAIM_LOCK" in text

    assert (
        "ProviderCapability.VOICE_PROFILE"
        not in text
    )

    assert (
        "long_document_audit_id=audit.audit_id"
        in text
    )

    _assert_order(
        text,
        "self._long_document_quota_admission.admit(",
        "with routing_operation as routing_scope:",
        "execution = self._orchestrator.execute(",
        "audit = self._audit_service.record(",
        "coordinator.complete_success(",
        "if self._observability is not None:",
    )


def test_container_provider_layering_is_legacy_routing_voice_workflow() -> None:
    text = _source(
        "app/v2/api/dependencies.py"
    )

    assert (
        "canonical_enterprise_routing_activation"
        in text
    )

    assert "workflow is None" in text
    assert "voice_aware_provider is None" in text

    _assert_order(
        text,
        "provider = build_rewrite_provider(",
        "EnterpriseRoutingAwareRewriteProvider(",
        "resolved_voice_provider = VoiceAwareRewriteProvider(",
        "resolved_workflow = RewriteWorkflow(",
    )

    assert text.count(
        "routing_operation_coordinator=("
    ) == 3
