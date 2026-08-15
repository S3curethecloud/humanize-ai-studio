from __future__ import annotations

from app.core.settings import Settings
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
from app.v2.config.voice_audit_auth import (
    VoiceAuditAuthenticitySettings,
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
from app.v2.services.enterprise_long_document_quota_admission_service import (
    EnterpriseLongDocumentQuotaAdmissionService,
)
from app.v2.services.enterprise_multi_candidate_quota_admission_service import (
    EnterpriseMultiCandidateQuotaAdmissionService,
)
from app.v2.services.enterprise_quota_runtime import (
    EnterpriseQuotaRuntime,
)
from app.v2.services.enterprise_quota_runtime_factory import (
    build_enterprise_quota_runtime,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseSingleRewriteQuotaAdmissionService,
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
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
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
        voice_audit_auth_settings: (VoiceAuditAuthenticitySettings | None) = None,
        quota_runtime: EnterpriseQuotaRuntime | None = None,
    ) -> None:
        resolved_persistence = persistence_settings or V2PersistenceSettings.from_environment()
        resolved_voice_audit_auth = (
            voice_audit_auth_settings or VoiceAuditAuthenticitySettings.from_environment()
        )
        voice_audit_authenticator = resolved_voice_audit_auth.build_authenticator()

        repositories = build_repository_bundle(resolved_persistence)

        unit_of_work = None

        if resolved_persistence.backend is PersistenceBackend.SQLITE:
            unit_of_work = build_unit_of_work(resolved_persistence)

        self.workspace = WorkspaceService(
            users=repositories.users,
            workspaces=repositories.workspaces,
            memberships=repositories.memberships,
            unit_of_work=unit_of_work,
        )

        self.history = RewriteHistoryService(
            workspace_service=self.workspace,
            history=repositories.history,
            voice_audit_authenticator=(voice_audit_authenticator),
        )

        self.voice_profiles = VoiceProfileService(
            workspace_service=self.workspace,
            profiles=repositories.voice_profiles,
        )

        self.voice_rewrite_guidance = VoiceRewriteGuidanceService(
            voice_profiles=self.voice_profiles,
        )

        resolved_workflow = workflow
        resolved_voice_provider = voice_aware_provider

        if resolved_workflow is None:
            if resolved_voice_provider is None:
                settings = Settings.from_environment()
                provider = build_rewrite_provider(settings)
                resolved_voice_provider = VoiceAwareRewriteProvider(
                    provider=provider,
                )

            resolved_workflow = RewriteWorkflow(
                provider=resolved_voice_provider,
            )

        self.claim_lock_preparation = ClaimLockPreparationService()

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
            workspace_service=self.workspace,
            repository=(long_document_audit_repository),
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
            workspace_service=self.workspace,
            repository=observability_repository,
            aggregator=(WorkspaceAnalyticsAggregator()),
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
            workspace_service=self.workspace,
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
        )

        self.rewrite = WorkspaceRewriteService(
            workspace_service=self.workspace,
            history_service=self.history,
            workflow=resolved_workflow,
            quota_admission=(single_rewrite_quota_admission),
            claim_lock_preparation_service=(self.claim_lock_preparation),
            observability=(self.single_rewrite_observability),
        )

        self.multi_candidate = MultiCandidateWorkspaceRewriteService(
            workspace_service=self.workspace,
            history_service=self.history,
            workflow=resolved_workflow,
            multi_candidate_quota_admission=(
                multi_candidate_quota_admission
            ),
            voice_guidance_service=self.voice_rewrite_guidance,
            voice_provider=resolved_voice_provider,
            claim_lock_preparation_service=(self.claim_lock_preparation),
            observability=(self.multi_candidate_observability),
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
