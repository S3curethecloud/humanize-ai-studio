from __future__ import annotations

from app.core.settings import Settings
from app.observability.metrics import metrics_registry
from app.providers.registry import (
    build_rewrite_provider,
)
from app.v2.config.enterprise_quota import (
    EnterpriseQuotaActivationSettings,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    ProviderTargetDeclarationSettings,
)
from app.v2.config.voice_audit_auth import (
    VoiceAuditAuthenticitySettings,
)
from app.v2.repositories.enterprise_claim_lock_policy_admin_mutations import (
    build_enterprise_claim_lock_policy_admin_mutation_repository,
)
from app.v2.repositories.enterprise_quota_admin_mutations import (
    build_enterprise_quota_admin_mutation_repository,
)
from app.v2.repositories.factory import (
    build_repository_bundle,
    build_unit_of_work,
)
from app.v2.repositories.long_document_audit import (
    InMemoryLongDocumentAuditRepository,
    LongDocumentAuditRepository,
    SQLiteLongDocumentAuditRepository,
)
from app.v2.repositories.observability import (
    InMemoryObservabilityEventRepository,
    ObservabilityEventRepository,
    SQLiteObservabilityEventRepository,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationService,
)
from app.v2.services.complex_rewrite_observability import (
    LongDocumentObservability,
    MultiCandidateObservability,
)
from app.v2.services.document_reconstructor import (
    DocumentReconstructor,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.enterprise_admin_audit_runtime import (
    EnterpriseAdminAuditRuntime,
)
from app.v2.services.enterprise_admin_audit_runtime_factory import (
    build_enterprise_admin_audit_runtime,
)
from app.v2.services.enterprise_authorization_runtime import (
    EnterpriseAuthorizationRuntime,
)
from app.v2.services.enterprise_authorization_runtime_factory import (
    build_enterprise_authorization_runtime,
)
from app.v2.services.enterprise_claim_lock_admin_service import (
    EnterpriseClaimLockAdminService,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeService,
)
from app.v2.services.enterprise_claim_lock_policy_repository_factory import (
    build_enterprise_claim_lock_policy_repository,
)
from app.v2.services.enterprise_long_document_quota_admission_service import (
    EnterpriseLongDocumentQuotaAdmissionService,
)
from app.v2.services.enterprise_membership_admin_service import (
    EnterpriseMembershipAdminService,
)
from app.v2.services.enterprise_multi_candidate_quota_admission_service import (
    EnterpriseMultiCandidateQuotaAdmissionService,
)
from app.v2.services.enterprise_quota_admin_service import (
    EnterpriseQuotaAdminService,
)
from app.v2.services.enterprise_quota_runtime import (
    EnterpriseQuotaRuntime,
)
from app.v2.services.enterprise_quota_runtime_factory import (
    build_enterprise_quota_limit_repository,
    build_enterprise_quota_runtime,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseSingleRewriteQuotaAdmissionService,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_ops_repository_factory import (
    build_evaluation_ops_repositories,
)
from app.v2.services.governed_eval_ops_runtime_factory import (
    build_governed_evaluation_ops_runtime,
)
from app.v2.services.long_document_audit_service import (
    LongDocumentAuditService,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluator,
)
from app.v2.services.long_document_rewrite_service import (
    LongDocumentWorkspaceRewriteService,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
)
from app.v2.services.observability_recording_service import (
    ObservabilityRecordingService,
)
from app.v2.services.provider_catalog_factory import (
    build_provider_catalog_repository,
)
from app.v2.services.provider_catalog_provisioning_service import (
    ProviderCatalogProvisioningService,
)
from app.v2.services.provider_routing_runtime_factory import (
    build_provider_routing_runtime,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.routing_eval_evidence_factory import (
    build_routing_eval_evidence_repositories,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceQueryService,
    RoutingEvidenceQueryService,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteOrchestrator,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)
from app.v2.services.single_rewrite_observability import (
    SingleRewriteObservability,
)
from app.v2.services.voice_aware_provider import (
    VoiceAwareRewriteProvider,
)
from app.v2.services.voice_aware_rewrite_service import (
    VoiceAwareWorkspaceRewriteService,
)
from app.v2.services.voice_profile_service import (
    VoiceProfileService,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceRewriteGuidanceService,
)
from app.v2.services.workspace_analytics_aggregator import (
    WorkspaceAnalyticsAggregator,
)
from app.v2.services.workspace_analytics_query_service import (
    WorkspaceAnalyticsQueryService,
)
from app.v2.services.workspace_rewrite_service import (
    WorkspaceRewriteService,
)
from app.v2.repositories.workspace_authority_provisioning import (
    build_atomic_workspace_authority_provisioner,
)
from app.v2.services.canonical_workspace_provisioning_service import (
    CanonicalWorkspaceProvisioningService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


class V2Services:
    def __init__(
        self,
        *,
        workflow: RewriteWorkflow | None = None,
        voice_aware_provider: (VoiceAwareRewriteProvider | None) = None,
        persistence_settings: (V2PersistenceSettings | None) = None,
        provider_settings: Settings | None = None,
        provider_target_settings: (
            ProviderTargetDeclarationSettings | None
        ) = None,
        voice_audit_auth_settings: (VoiceAuditAuthenticitySettings | None) = None,
        quota_runtime: EnterpriseQuotaRuntime | None = None,
        enterprise_authorization_runtime: (
            EnterpriseAuthorizationRuntime | None
        ) = None,
        enterprise_admin_audit_runtime: (
            EnterpriseAdminAuditRuntime | None
        ) = None,
    ) -> None:
        resolved_persistence = persistence_settings or V2PersistenceSettings.from_environment()
        resolved_provider_settings = (
            provider_settings or Settings.from_environment()
        )
        resolved_provider_targets = (
            provider_target_settings
            or ProviderTargetDeclarationSettings.from_environment()
        )
        resolved_voice_audit_auth = (
            voice_audit_auth_settings or VoiceAuditAuthenticitySettings.from_environment()
        )
        voice_audit_authenticator = resolved_voice_audit_auth.build_authenticator()

        repositories = build_repository_bundle(resolved_persistence)

        self.routing_eval_evidence_repositories = (
            build_routing_eval_evidence_repositories(
                resolved_persistence,
            )
        )

        self.provider_target_declarations = (
            resolved_provider_targets
        )
        self.provider_catalog = (
            build_provider_catalog_repository(
                resolved_persistence,
            )
        )
        self.provider_catalog_provisioning = (
            ProviderCatalogProvisioningService(
                catalog=self.provider_catalog,
            )
        )
        self.provider_catalog_provisioning_result = (
            self.provider_catalog_provisioning.provision(
                targets=resolved_provider_targets.targets,
            )
        )
        self.provider_routing = (
            build_provider_routing_runtime(
                settings=resolved_provider_settings,
                catalog=self.provider_catalog,
                evidence=(
                    self.routing_eval_evidence_repositories.routing
                ),
                telemetry=metrics_registry,
            )
        )
        self.routing_execution_evidence = (
            self.provider_routing.execution_evidence
        )
        self.routing_decision_evidence = (
            self.provider_routing.decision_evidence
        )

        self.evaluation_evidence = EvaluationEvidenceService(
            repository=(
                self.routing_eval_evidence_repositories.evaluation
            ),
            telemetry=metrics_registry,
        )

        self.evaluation_ops_repositories = (
            build_evaluation_ops_repositories(
                resolved_persistence,
            )
        )
        self.evaluation_ops = (
            build_governed_evaluation_ops_runtime(
                settings=resolved_provider_settings,
                catalog=self.provider_catalog,
                datasets=(
                    self.evaluation_ops_repositories.datasets
                ),
                runs=self.evaluation_ops_repositories.runs,
                evidence=self.evaluation_evidence,
            )
        )

        self.routing_evidence_query = (
            RoutingEvidenceQueryService(
                repository=(
                    self.routing_eval_evidence_repositories.routing
                ),
            )
        )
        self.evaluation_evidence_query = (
            EvaluationEvidenceQueryService(
                repository=(
                    self.routing_eval_evidence_repositories.evaluation
                ),
            )
        )

        self.enterprise_admin_audit = (
            enterprise_admin_audit_runtime
            or build_enterprise_admin_audit_runtime(
                resolved_persistence,
            )
        )

        self.enterprise_authorization = (
            enterprise_authorization_runtime
            or build_enterprise_authorization_runtime(
                resolved_persistence,
            )
        )

        self.enterprise_claim_lock_policies = (
            build_enterprise_claim_lock_policy_repository(
                resolved_persistence,
            )
        )

        self.enterprise_claim_lock_policy_admin_mutations = (
            build_enterprise_claim_lock_policy_admin_mutation_repository(
                policies=self.enterprise_claim_lock_policies,
                audit=self.enterprise_admin_audit.repository,
            )
        )

        self.claim_lock_admin = EnterpriseClaimLockAdminService(
            policies=self.enterprise_claim_lock_policies,
            authorization_resolver=(
                self.enterprise_authorization.authorization_resolver
            ),
            audit_recording=(
                self.enterprise_admin_audit.recording
            ),
            atomic_mutations=(
                self.enterprise_claim_lock_policy_admin_mutations
            ),
        )

        self.workspace_authorization = (
            WorkspaceAuthorizationGate(
                resolver=(
                    self.enterprise_authorization
                    .authorization_resolver
                ),
            )
        )

        self.membership_admin = EnterpriseMembershipAdminService(
            memberships=(
                self.enterprise_authorization.memberships
            ),
            authorization_resolver=(
                self.enterprise_authorization.authorization_resolver
            ),
        )

        quota_limits = (
            quota_runtime.limits
            if quota_runtime is not None
            else build_enterprise_quota_limit_repository(
                resolved_persistence,
            )
        )

        self.enterprise_quota_admin_mutations = (
            build_enterprise_quota_admin_mutation_repository(
                limits=quota_limits,
                audit=(
                    self.enterprise_admin_audit.repository
                ),
            )
        )

        self.quota_admin = EnterpriseQuotaAdminService(
            limits=quota_limits,
            authorization_resolver=(
                self.enterprise_authorization.authorization_resolver
            ),
            audit_recording=(
                self.enterprise_admin_audit.recording
            ),
            atomic_mutations=(
                self.enterprise_quota_admin_mutations
            ),
        )

        unit_of_work = None

        if resolved_persistence.backend is PersistenceBackend.SQLITE:
            unit_of_work = build_unit_of_work(resolved_persistence)

        self.workspace_authority_provisioner = (
            build_atomic_workspace_authority_provisioner(
                persistence_settings=resolved_persistence,
                legacy_workspaces=repositories.workspaces,
                legacy_memberships=repositories.memberships,
                enterprise_organizations=(
                    self.enterprise_authorization.organizations
                ),
                enterprise_workspaces=(
                    self.enterprise_authorization.workspaces
                ),
                enterprise_memberships=(
                    self.enterprise_authorization.memberships
                ),
            )
        )

        self.workspace_provisioning = (
            CanonicalWorkspaceProvisioningService(
                users=repositories.users,
                provisioner=(
                    self.workspace_authority_provisioner
                ),
            )
        )

        self.workspace = WorkspaceService(
            users=repositories.users,
            workspaces=repositories.workspaces,
            memberships=repositories.memberships,
            unit_of_work=unit_of_work,
        )

        self.history = RewriteHistoryService(
            history=repositories.history,
            voice_audit_authenticator=(voice_audit_authenticator),
            authorization_gate=self.workspace_authorization,
        )

        self.voice_profiles = VoiceProfileService(
            profiles=repositories.voice_profiles,
            authorization_gate=self.workspace_authorization,
        )

        self.voice_rewrite_guidance = VoiceRewriteGuidanceService(
            voice_profiles=self.voice_profiles,
        )

        resolved_workflow = workflow
        resolved_voice_provider = voice_aware_provider

        if resolved_workflow is None:
            if resolved_voice_provider is None:
                provider = build_rewrite_provider(
                    resolved_provider_settings
                )
                resolved_voice_provider = VoiceAwareRewriteProvider(
                    provider=provider,
                )

            resolved_workflow = RewriteWorkflow(
                provider=resolved_voice_provider,
            )

        self.claim_lock_preparation = ClaimLockPreparationService()

        self.enterprise_claim_lock_runtime = (
            EnterpriseClaimLockRuntimeService(
                policies=self.enterprise_claim_lock_policies,
                authorization_gate=self.workspace_authorization,
                preparation_service=self.claim_lock_preparation,
            )
        )

        single_rewrite_quota_admission = None
        multi_candidate_quota_admission = None
        long_document_quota_admission = None

        if quota_runtime is not None:
            single_rewrite_quota_admission = (
                EnterpriseSingleRewriteQuotaAdmissionService(
                    runtime_context=quota_runtime.runtime_context,
                    enforcement=quota_runtime.enforcement,
                )
            )
            multi_candidate_quota_admission = (
                EnterpriseMultiCandidateQuotaAdmissionService(
                    runtime_context=quota_runtime.runtime_context,
                    enforcement=quota_runtime.enforcement,
                )
            )
            long_document_quota_admission = (
                EnterpriseLongDocumentQuotaAdmissionService(
                    runtime_context=quota_runtime.runtime_context,
                    enforcement=quota_runtime.enforcement,
                )
            )

        if resolved_persistence.backend is PersistenceBackend.MEMORY:
            long_document_audit_repository: LongDocumentAuditRepository = (
                InMemoryLongDocumentAuditRepository()
            )
        elif resolved_persistence.backend is PersistenceBackend.SQLITE:
            if resolved_persistence.sqlite_path is None:
                raise ValueError("SQLite persistence requires a database path.")

            long_document_audit_repository = SQLiteLongDocumentAuditRepository(
                database_path=(resolved_persistence.sqlite_path),
            )
        else:
            raise RuntimeError("Unsupported long-document persistence backend.")

        self.long_document_audit = LongDocumentAuditService(
            repository=(long_document_audit_repository),
            authorization_gate=self.workspace_authorization,
        )

        if resolved_persistence.backend is PersistenceBackend.MEMORY:
            observability_repository: ObservabilityEventRepository = (
                InMemoryObservabilityEventRepository()
            )
        elif resolved_persistence.backend is PersistenceBackend.SQLITE:
            if resolved_persistence.sqlite_path is None:
                raise ValueError("SQLite persistence requires a database path.")

            observability_repository = SQLiteObservabilityEventRepository(
                database_path=(resolved_persistence.sqlite_path),
            )
        else:
            raise RuntimeError("Unsupported observability persistence backend.")

        self.observability_recording = ObservabilityRecordingService(
            repository=(observability_repository),
        )

        self.workspace_analytics = WorkspaceAnalyticsQueryService(
            repository=observability_repository,
            aggregator=(WorkspaceAnalyticsAggregator()),
            authorization_gate=self.workspace_authorization,
        )

        self.single_rewrite_observability = SingleRewriteObservability(
            recording_service=(self.observability_recording),
        )

        self.multi_candidate_observability = MultiCandidateObservability(
            recording_service=(self.observability_recording),
        )

        self.long_document_observability = LongDocumentObservability(
            recording_service=(self.observability_recording),
        )

        self.long_document = LongDocumentWorkspaceRewriteService(
            claim_lock_preparation_service=(self.claim_lock_preparation),
            structure_detector=(DocumentStructureDetector()),
            planner=SectionRewritePlanner(),
            orchestrator=(
                SectionRewriteOrchestrator(
                    workflow=resolved_workflow,
                )
            ),
            control_evaluator=(LongDocumentControlEvaluator()),
            reconstructor=DocumentReconstructor(),
            audit_service=(self.long_document_audit),
            long_document_quota_admission=(long_document_quota_admission),
            observability=(self.long_document_observability),
            authorization_gate=self.workspace_authorization,
        )

        self.rewrite = WorkspaceRewriteService(
            history_service=self.history,
            workflow=resolved_workflow,
            quota_admission=(single_rewrite_quota_admission),
            enterprise_claim_lock_runtime_service=(
                self.enterprise_claim_lock_runtime
            ),
            observability=(self.single_rewrite_observability),
            authorization_gate=self.workspace_authorization,
        )

        self.multi_candidate = MultiCandidateWorkspaceRewriteService(
            history_service=self.history,
            workflow=resolved_workflow,
            multi_candidate_quota_admission=(
                multi_candidate_quota_admission
            ),
            voice_guidance_service=self.voice_rewrite_guidance,
            voice_provider=resolved_voice_provider,
            claim_lock_preparation_service=(self.claim_lock_preparation),
            observability=(self.multi_candidate_observability),
            authorization_gate=self.workspace_authorization,
        )

        self.voice_rewrite = None

        if resolved_voice_provider is not None:
            self.voice_rewrite = VoiceAwareWorkspaceRewriteService(
                rewrite_service=self.rewrite,
                guidance_service=(self.voice_rewrite_guidance),
                provider=resolved_voice_provider,
            )


def build_v2_services_from_environment() -> V2Services:
    persistence_settings = (
        V2PersistenceSettings.from_environment()
    )
    quota_activation = (
        EnterpriseQuotaActivationSettings.from_environment()
    )

    quota_runtime = (
        build_enterprise_quota_runtime(
            persistence_settings,
        )
        if quota_activation.enabled
        else None
    )

    return V2Services(
        persistence_settings=persistence_settings,
        quota_runtime=quota_runtime,
    )


services = build_v2_services_from_environment()
