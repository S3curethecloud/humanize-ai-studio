from __future__ import annotations

from app.core.settings import Settings
from app.providers.registry import (
    build_rewrite_provider,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.factory import (
    build_repository_bundle,
    build_unit_of_work,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
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
        persistence_settings: (V2PersistenceSettings | None) = None,
    ) -> None:
        resolved_persistence = persistence_settings or V2PersistenceSettings.from_environment()

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
        )

        self.voice_profiles = VoiceProfileService(
            workspace_service=self.workspace,
            profiles=repositories.voice_profiles,
        )

        self.voice_rewrite_guidance = VoiceRewriteGuidanceService(
            voice_profiles=self.voice_profiles,
        )

        resolved_workflow = workflow

        if resolved_workflow is None:
            settings = Settings.from_environment()
            provider = build_rewrite_provider(settings)
            resolved_workflow = RewriteWorkflow(provider=provider)

        self.rewrite = WorkspaceRewriteService(
            workspace_service=self.workspace,
            history_service=self.history,
            workflow=resolved_workflow,
        )


services = V2Services()
