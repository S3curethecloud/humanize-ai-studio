from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)

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
from app.providers.exceptions import (
    RewriteProviderTransportError,
)
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.services.enterprise_provider_routing_operation_coordinator import (
    ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE,
)
from app.v2.services.enterprise_routing_aware_provider import (
    EnterpriseProviderRoutingNoEligibleTargetError,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)
from app.v2.services.routing_eval_evidence_query_service import (
    RoutingEvidenceNotFoundError,
)


TARGET_ID = "deterministic-primary"

PROVIDER_REQUIRED_TEXT = (
    "The policy engine evaluates every proposed "
    "tool call before execution."
)

BYPASS_TEXT = (
    "The gateway validates identity context and "
    "creates an audit trace."
)


class _FailingDeterministicProvider:
    @property
    def provider_name(
        self,
    ) -> str:
        return DETERMINISTIC_PROVIDER_ID

    def rewrite(
        self,
        request: RewriteRequest,
    ):
        del request

        raise RewriteProviderTransportError(
            "simulated routed provider transport failure"
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
    capabilities: frozenset[
        ProviderCapability
    ],
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
                        capabilities=capabilities,
                    )
                ),
                enabled=True,
            ),
        ),
    )


def _services(
    monkeypatch: pytest.MonkeyPatch,
    *,
    capabilities: frozenset[
        ProviderCapability
    ],
) -> V2Services:
    monkeypatch.delenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        raising=False,
    )

    return V2Services(
        persistence_settings=_memory_persistence(),
        provider_settings=_provider_settings(),
        provider_target_settings=(
            _target_settings(
                capabilities
            )
        ),
    )


def _provision_workspace(
    services: V2Services,
    *,
    label: str,
) -> tuple[
    str,
    str,
]:
    owner = services.workspace.create_user(
        email=(
            f"routing-c2b-{label}@example.com"
        ),
        display_name=(
            f"Routing C2B {label} Owner"
        ),
    )

    workspace = (
        services.workspace_provisioning
        .create_workspace(
            user_id=owner.user_id,
            name=(
                f"Routing C2B {label} Workspace"
            ),
        )
    )

    return (
        owner.user_id,
        workspace.workspace_id,
    )


def _create_policy(
    services: V2Services,
    *,
    workspace_id: str,
    user_id: str,
    status: str = "active",
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
                EnterpriseProviderRoutingPolicyStatus(
                    status
                )
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


def _set_test_ids(
    services: V2Services,
    *,
    operation_id: str,
    evidence_ids: tuple[
        str,
        ...,
    ] = (),
) -> None:
    operation_service = (
        services
        .enterprise_provider_routing_operation_service
    )

    routing_provider = (
        services.enterprise_routing_aware_provider
    )

    assert operation_service is not None
    assert routing_provider is not None

    operation_service._operation_id_factory = (
        lambda: operation_id
    )

    remaining = iter(
        evidence_ids
    )

    def evidence_id_factory(
    ) -> str:
        try:
            return next(
                remaining
            )
        except StopIteration as exc:
            raise AssertionError(
                "unexpected provider routing "
                "evidence reservation"
            ) from exc

    routing_provider._evidence_id_factory = (
        evidence_id_factory
    )


def _request(
    *,
    text: str,
    intensity: RewriteIntensity,
) -> RewriteRequest:
    return RewriteRequest(
        text=text,
        document_type=DocumentType.GENERAL,
        audience="engineering leadership",
        tone="natural and clear",
        intensity=intensity,
        preserve_numbers=True,
        preserve_dates=True,
    )


def _operation(
    services: V2Services,
    operation_id: str,
):
    repository = (
        services.enterprise_provider_routing_operations
    )

    assert repository is not None

    operation = repository.get(
        operation_id
    )

    assert operation is not None

    return operation


def _assert_no_history(
    services: V2Services,
    *,
    workspace_id: str,
    user_id: str,
) -> None:
    assert (
        services.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        == ()
    )


@pytest.mark.parametrize(
    "policy_status",
    (
        None,
        "disabled",
    ),
    ids=(
        "no-policy",
        "disabled-policy",
    ),
)
def test_no_or_disabled_policy_preserves_legacy_execution_without_enterprise_operation(
    monkeypatch: pytest.MonkeyPatch,
    policy_status: str | None,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label=(
                "legacy-"
                + (
                    policy_status
                    or "none"
                )
            ),
        )
    )

    if policy_status is not None:
        _create_policy(
            services,
            workspace_id=workspace_id,
            user_id=user_id,
            status=policy_status,
        )

    operation_id = (
        "enterprise_routing_operation_legacy"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
    )

    result = services.rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=_request(
            text=PROVIDER_REQUIRED_TEXT,
            intensity=(
                RewriteIntensity.NATURAL_REWRITE
            ),
        ),
    )

    assert (
        result.response.rewrite_necessity
        .provider_required
        is True
    )

    assert (
        result.history.workspace_id
        == workspace_id
    )

    repository = (
        services.enterprise_provider_routing_operations
    )

    assert repository is not None

    assert (
        repository.get(
            operation_id
        )
        is None
    )


def test_active_policy_deterministic_bypass_records_no_provider_execution_and_zero_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="bypass",
        )
    )

    policy = _create_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_id = (
        "enterprise_routing_operation_bypass"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
    )

    result = services.rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=_request(
            text=BYPASS_TEXT,
            intensity=(
                RewriteIntensity.LIGHT_EDIT
            ),
        ),
    )

    assert (
        result.response.rewrite_necessity
        .provider_required
        is False
    )

    operation = _operation(
        services,
        operation_id,
    )

    assert operation.status.value == (
        "no_provider_execution"
    )

    assert (
        operation.routing_evidence_bindings
        == ()
    )

    assert (
        operation.rewrite_history_id
        == result.history.rewrite_id
    )

    assert (
        operation.long_document_audit_id
        is None
    )

    assert operation.policy_id == (
        policy.policy_id
    )

    assert (
        ProviderCapability.REWRITE
        in operation.required_capabilities
    )

    assert (
        ProviderCapability.CLAIM_LOCK
        in operation.required_capabilities
    )


def test_active_policy_provider_success_links_recorded_platform_evidence_and_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="success",
        )
    )

    policy = _create_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_id = (
        "enterprise_routing_operation_success"
    )

    evidence_id = (
        "routing_evidence_success"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
        evidence_ids=(
            evidence_id,
        ),
    )

    result = services.rewrite.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=_request(
            text=PROVIDER_REQUIRED_TEXT,
            intensity=(
                RewriteIntensity.NATURAL_REWRITE
            ),
        ),
    )

    assert (
        result.response.rewrite_necessity
        .provider_required
        is True
    )

    operation = _operation(
        services,
        operation_id,
    )

    assert (
        operation.status.value
        == "succeeded"
    )

    assert (
        operation.policy_id
        == policy.policy_id
    )

    assert (
        operation.policy_revision
        == policy.revision
    )

    assert (
        operation.rewrite_history_id
        == result.history.rewrite_id
    )

    assert (
        operation.long_document_audit_id
        is None
    )

    assert (
        len(
            operation.routing_evidence_bindings
        )
        == 1
    )

    binding = (
        operation.routing_evidence_bindings[
            0
        ]
    )

    assert binding.evidence_id == evidence_id
    assert binding.status.value == "recorded"

    evidence = (
        services.routing_evidence_query.get(
            evidence_id=evidence_id,
        )
    )

    assert (
        evidence.decision.status.value
        == "selected"
    )

    assert (
        evidence.execution_outcome.value
        == "succeeded"
    )

    assert (
        evidence.executed_target_id
        == TARGET_ID
    )

    assert (
        evidence.execution_fallback_used
        is False
    )


def test_active_policy_no_eligible_target_fails_with_recorded_nonexecution_evidence_and_no_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="no-eligible",
        )
    )

    _create_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_id = (
        "enterprise_routing_operation_no_eligible"
    )

    evidence_id = (
        "routing_evidence_no_eligible"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
        evidence_ids=(
            evidence_id,
        ),
    )

    with pytest.raises(
        EnterpriseProviderRoutingNoEligibleTargetError,
        match="no eligible provider target",
    ):
        services.rewrite.execute(
            workspace_id=workspace_id,
            user_id=user_id,
            request=_request(
                text=PROVIDER_REQUIRED_TEXT,
                intensity=(
                    RewriteIntensity.NATURAL_REWRITE
                ),
            ),
            voice_profile_id=(
                "voice_profile_required"
            ),
        )

    operation = _operation(
        services,
        operation_id,
    )

    assert operation.status.value == "failed"

    assert operation.failure_code == (
        ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE
    )

    assert operation.rewrite_history_id is None
    assert operation.long_document_audit_id is None

    assert (
        ProviderCapability.VOICE_PROFILE
        in operation.required_capabilities
    )

    assert (
        len(
            operation.routing_evidence_bindings
        )
        == 1
    )

    binding = (
        operation.routing_evidence_bindings[
            0
        ]
    )

    assert binding.evidence_id == evidence_id
    assert binding.status.value == "recorded"

    evidence = (
        services.routing_evidence_query.get(
            evidence_id=evidence_id,
        )
    )

    assert (
        evidence.decision.status.value
        == "no_eligible_target"
    )

    assert (
        evidence.execution_outcome.value
        == "not_executed"
    )

    assert evidence.executed_target_id is None
    assert evidence.attempts == ()

    _assert_no_history(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )


def test_active_policy_provider_failure_records_platform_failure_before_workspace_failure_terminalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="provider-failure",
        )
    )

    _create_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_id = (
        "enterprise_routing_operation_provider_failure"
    )

    evidence_id = (
        "routing_evidence_provider_failure"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
        evidence_ids=(
            evidence_id,
        ),
    )

    bindings = (
        services.provider_routing
        .execution_adapter
        ._bindings
    )

    assert TARGET_ID in bindings

    bindings[
        TARGET_ID
    ] = _FailingDeterministicProvider()

    with pytest.raises(
        RewriteProviderTransportError,
        match="simulated routed provider transport failure",
    ):
        services.rewrite.execute(
            workspace_id=workspace_id,
            user_id=user_id,
            request=_request(
                text=PROVIDER_REQUIRED_TEXT,
                intensity=(
                    RewriteIntensity.NATURAL_REWRITE
                ),
            ),
        )

    operation = _operation(
        services,
        operation_id,
    )

    assert operation.status.value == "failed"

    assert operation.failure_code == (
        ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE
    )

    assert (
        len(
            operation.routing_evidence_bindings
        )
        == 1
    )

    binding = (
        operation.routing_evidence_bindings[
            0
        ]
    )

    assert binding.evidence_id == evidence_id
    assert binding.status.value == "recorded"

    evidence = (
        services.routing_evidence_query.get(
            evidence_id=evidence_id,
        )
    )

    assert (
        evidence.execution_outcome.value
        == "failed"
    )

    assert evidence.executed_target_id is None

    assert len(evidence.attempts) == 1

    attempt = evidence.attempts[0]

    assert (
        attempt.outcome.value
        == "provider_error"
    )

    assert (
        attempt.failure_category.value
        == "transport"
    )

    _assert_no_history(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )


def test_pre_evidence_routing_failure_preserves_reserved_binding_without_fabricating_platform_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="pre-evidence",
        )
    )

    _create_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_id = (
        "enterprise_routing_operation_pre_evidence"
    )

    evidence_id = (
        "routing_evidence_pre_evidence"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
        evidence_ids=(
            evidence_id,
        ),
    )

    def fail_before_platform_evidence(
        **_kwargs: object,
    ):
        raise RuntimeError(
            "simulated pre-evidence routing failure"
        )

    monkeypatch.setattr(
        services.provider_routing.routing,
        "route_and_execute",
        fail_before_platform_evidence,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated pre-evidence routing failure",
    ):
        services.rewrite.execute(
            workspace_id=workspace_id,
            user_id=user_id,
            request=_request(
                text=PROVIDER_REQUIRED_TEXT,
                intensity=(
                    RewriteIntensity.NATURAL_REWRITE
                ),
            ),
        )

    operation = _operation(
        services,
        operation_id,
    )

    assert operation.status.value == "failed"

    assert operation.failure_code == (
        ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE
    )

    assert (
        len(
            operation.routing_evidence_bindings
        )
        == 1
    )

    binding = (
        operation.routing_evidence_bindings[
            0
        ]
    )

    assert binding.evidence_id == evidence_id
    assert binding.status.value == "reserved"

    with pytest.raises(
        RoutingEvidenceNotFoundError,
    ):
        services.routing_evidence_query.get(
            evidence_id=evidence_id,
        )

    _assert_no_history(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )


def test_long_document_success_links_audit_without_voice_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _services(
        monkeypatch,
        capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.CLAIM_LOCK,
                ProviderCapability.LONG_DOCUMENT,
            }
        ),
    )

    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="long-success",
        )
    )

    policy = _create_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_id = (
        "enterprise_routing_operation_long_success"
    )

    _set_test_ids(
        services,
        operation_id=operation_id,
    )

    result = services.long_document.execute(
        workspace_id=workspace_id,
        user_id=user_id,
        request=_request(
            text=BYPASS_TEXT,
            intensity=(
                RewriteIntensity.LIGHT_EDIT
            ),
        ),
    )

    operation = _operation(
        services,
        operation_id,
    )

    assert (
        operation.status.value
        == "no_provider_execution"
    )

    assert (
        operation.policy_id
        == policy.policy_id
    )

    assert (
        operation.long_document_audit_id
        == result.audit.audit_id
    )

    assert operation.rewrite_history_id is None

    assert (
        operation.routing_evidence_bindings
        == ()
    )

    assert (
        ProviderCapability.REWRITE
        in operation.required_capabilities
    )

    assert (
        ProviderCapability.LONG_DOCUMENT
        in operation.required_capabilities
    )

    assert (
        ProviderCapability.CLAIM_LOCK
        in operation.required_capabilities
    )

    assert (
        ProviderCapability.VOICE_PROFILE
        not in operation.required_capabilities
    )
