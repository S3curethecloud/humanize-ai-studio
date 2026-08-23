from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.v2.api.dependencies import V2Services


def _services() -> V2Services:
    return V2Services()


def _provision_workspace(
    services: V2Services,
    *,
    label: str,
) -> tuple[str, str]:
    owner = services.workspace.create_user(
        email=f"cross-tenant-{label}-{uuid4().hex}@example.com",
        display_name=f"Cross Tenant {label} Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=owner.user_id,
        name=f"Cross Tenant Workspace {label}",
    )

    return owner.user_id, workspace.workspace_id


def _period() -> tuple[datetime, datetime]:
    end = datetime.now(UTC)

    return (
        end - timedelta(hours=1),
        end,
    )


def test_workspace_a_owner_cannot_read_workspace_b_history() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    _, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.history.list_workspace_history(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
        )


def test_workspace_a_owner_cannot_query_workspace_b_analytics() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    _, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    period_start, period_end = _period()

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.workspace_analytics.query(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            period_start=period_start,
            period_end=period_end,
        )


def test_workspace_a_owner_cannot_execute_rewrite_in_workspace_b() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from app.domain.models import (
        DocumentType,
        RewriteIntensity,
        RewriteRequest,
    )

    request = RewriteRequest(
        text="Cross-tenant rewrite must fail closed.",
        document_type=DocumentType.GENERAL,
        audience="general audience",
        tone="natural",
        intensity=RewriteIntensity.NATURAL_REWRITE,
        preserve_numbers=True,
        preserve_dates=True,
    )

    before_records = services.history.list_workspace_history(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert before_records == ()

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.rewrite.execute(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            request=request,
        )

    after_records = services.history.list_workspace_history(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert after_records == ()


def test_workspace_a_owner_cannot_execute_multi_candidate_rewrite_in_workspace_b() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from app.domain.models import (
        DocumentType,
        RewriteIntensity,
        RewriteRequest,
    )

    request = RewriteRequest(
        text="Cross-tenant multi-candidate rewrite must fail closed.",
        document_type=DocumentType.GENERAL,
        audience="general audience",
        tone="natural",
        intensity=RewriteIntensity.NATURAL_REWRITE,
        preserve_numbers=True,
        preserve_dates=True,
    )

    before_records = services.history.list_workspace_history(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert before_records == ()

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.multi_candidate.execute(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            request=request,
            candidate_count=2,
        )

    after_records = services.history.list_workspace_history(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert after_records == ()


def test_workspace_a_owner_cannot_execute_long_document_rewrite_in_workspace_b() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from app.domain.models import (
        DocumentType,
        RewriteIntensity,
        RewriteRequest,
    )

    request = RewriteRequest(
        text=(
            "First protected section.\n\n"
            "Second protected section."
        ),
        document_type=DocumentType.GENERAL,
        audience="general audience",
        tone="natural",
        intensity=RewriteIntensity.NATURAL_REWRITE,
        preserve_numbers=True,
        preserve_dates=True,
    )

    before_audit = services.long_document_audit.list_workspace(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert before_audit == ()

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.long_document.execute(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            request=request,
        )

    after_audit = services.long_document_audit.list_workspace(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert after_audit == ()


def test_workspace_a_owner_cannot_read_workspace_b_voice_profile() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from app.v2.domain.models import VoiceSourceSample

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        name="Workspace B Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id=f"cross-tenant-{uuid4().hex}",
                text=(
                    "I communicate decisions clearly and preserve "
                    "the context required for the next action."
                ),
            ),
        ),
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_profiles.get_profile(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            profile_id=profile.profile_id,
        )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_profiles.list_profiles(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
        )


def test_workspace_a_owner_cannot_use_workspace_b_voice_profile() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from app.v2.domain.models import VoiceSourceSample

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        name="Workspace B Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id=f"cross-tenant-{uuid4().hex}",
                text=(
                    "I explain decisions with enough context to "
                    "make the next step clear and defensible."
                ),
            ),
        ),
    )

    analyzed = services.voice_profiles.analyze_profile(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        profile_id=profile.profile_id,
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_rewrite_guidance.build_guidance(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            profile_id=analyzed.profile.profile_id,
        )


def test_workspace_a_owner_cannot_manage_workspace_b_voice_profile() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from app.v2.domain.models import VoiceSourceSample

    profile = services.voice_profiles.create_profile(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        name="Workspace B Voice",
        source_samples=(
            VoiceSourceSample(
                sample_id=f"cross-tenant-{uuid4().hex}",
                text=(
                    "I write with practical detail and preserve "
                    "the information needed to act confidently."
                ),
            ),
        ),
    )

    current = services.voice_profiles.get_profile(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        profile_id=profile.profile_id,
    )

    candidate = current.model_copy(
        update={"name": "Forbidden Cross-Tenant Update"},
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_profiles.update_profile(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            profile=candidate,
        )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_profiles.analyze_profile(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            profile_id=profile.profile_id,
        )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.voice_profiles.archive_profile(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            profile_id=profile.profile_id,
        )

    unchanged = services.voice_profiles.get_profile(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        profile_id=profile.profile_id,
    )

    assert unchanged.name == "Workspace B Voice"
    assert unchanged.status.value == "active"


def test_workspace_a_owner_cannot_read_workspace_b_audit_record() -> None:
    services = _services()

    user_a_id, workspace_a_id = _provision_workspace(
        services,
        label="A",
    )
    owner_b_id, workspace_b_id = _provision_workspace(
        services,
        label="B",
    )

    assert workspace_a_id != workspace_b_id

    from tests.v2.test_long_document_audit_persistence import (
        _artifacts,
    )

    evaluation, reconstruction = _artifacts()

    record = services.long_document_audit.record(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        evaluation=evaluation,
        reconstruction=reconstruction,
    )

    loaded_by_b = services.long_document_audit.get(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        audit_id=record.audit_id,
    )

    assert loaded_by_b == record

    listed_by_b = services.long_document_audit.list_workspace(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
    )

    assert record in listed_by_b

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.long_document_audit.get(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
            audit_id=record.audit_id,
        )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        services.long_document_audit.list_workspace(
            workspace_id=workspace_b_id,
            user_id=user_a_id,
        )

    still_loaded_by_b = services.long_document_audit.get(
        workspace_id=workspace_b_id,
        user_id=owner_b_id,
        audit_id=record.audit_id,
    )

    assert still_loaded_by_b == record
