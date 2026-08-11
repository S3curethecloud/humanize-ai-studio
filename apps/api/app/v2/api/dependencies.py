from __future__ import annotations

from app.core.settings import Settings
from app.providers.registry import (
    build_rewrite_provider,
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
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationService,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
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

        self.rewrite = WorkspaceRewriteService(
            workspace_service=self.workspace,
            history_service=self.history,
            workflow=resolved_workflow,
            claim_lock_preparation_service=(self.claim_lock_preparation),
        )

        self.voice_rewrite = None

        if resolved_voice_provider is not None:
            self.voice_rewrite = VoiceAwareWorkspaceRewriteService(
                rewrite_service=self.rewrite,
                guidance_service=(self.voice_rewrite_guidance),
                provider=resolved_voice_provider,
            )


services = V2Services()
