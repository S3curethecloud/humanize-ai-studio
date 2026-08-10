from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class RewriteRecordStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class UserRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    email: str
    display_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_id: str
    name: str
    created_by_user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceMembership(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RewriteHistoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    rewrite_id: str
    workspace_id: str
    user_id: str
    trace_id: str

    source_text: str
    rewritten_text: str

    document_type: str
    audience: str
    tone: str
    intensity: str

    provider_name: str
    model_name: str
    prompt_version: str

    fallback_used: bool
    verification_decision: str
    editorial_quality_decision: str

    status: RewriteRecordStatus = RewriteRecordStatus.COMPLETED

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
