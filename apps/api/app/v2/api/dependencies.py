from __future__ import annotations

from app.core.settings import Settings
from app.providers.registry import (
    build_rewrite_provider,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
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


class V2Services:
    def __init__(
        self,
        *,
        workflow: RewriteWorkflow | None = None,
    ) -> None:
        users = InMemoryUserRepository()
        workspaces = InMemoryWorkspaceRepository()
        memberships = InMemoryMembershipRepository()
        history = InMemoryRewriteHistoryRepository()

        self.workspace = WorkspaceService(
            users=users,
            workspaces=workspaces,
            memberships=memberships,
        )

        self.history = RewriteHistoryService(
            workspace_service=self.workspace,
            history=history,
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
