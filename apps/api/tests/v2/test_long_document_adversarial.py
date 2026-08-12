from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.domain.models import (
    EditorialQualityDecision,
    EditorialQualityResult,
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
    ReleaseDecision,
    RewriteNecessityEvidence,
    RewriteRequest,
    RewriteResponse,
    VerificationResult,
)
from app.main import app
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.long_document_audit import (
    LongDocumentAuditRecord,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)

client = TestClient(app)

SOURCE = (
    "# Overview\n"
    "Project Atlas completed the review.\n"
    "\n"
    "## Financials\n"
    "Revenue was 42 million in 2025.\n"
)

CROSS_SECTION_SOURCE = (
    "# First\n"
    "Project Atlas completed the first review.\n"
    "\n"
    "## Second\n"
    "Project Atlas completed the second review.\n"
)

CRLF_SOURCE = (
    "# Overview\r\n"
    "Project Atlas completed the review.\r\n"
    "\r\n"
    "## Financials\r\n"
    "Revenue was 42 million in 2025.\r\n"
)


@dataclass(frozen=True)
class Scenario:
    replace_from: str | None = None
    replace_to: str = ""
    source_text_override: str | None = None
    verification_decision: ReleaseDecision = ReleaseDecision.PASS


class AdversarialWorkflow:
    def __init__(
        self,
        scenarios: tuple[
            Scenario,
            ...,
        ] = (),
    ) -> None:
        self._scenarios = scenarios
        self.requests: list[RewriteRequest] = []

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        index = len(self.requests)
        self.requests.append(request)

        scenario = self._scenarios[index] if index < len(self._scenarios) else Scenario()

        rewritten_text = request.text

        if scenario.replace_from is not None:
            rewritten_text = rewritten_text.replace(
                scenario.replace_from,
                scenario.replace_to,
            )

        source_text = (
            scenario.source_text_override
            if scenario.source_text_override is not None
            else request.text
        )

        return _response(
            source_text=source_text,
            rewritten_text=rewritten_text,
            trace_id=f"trace-i-{index + 1}",
            decision=(scenario.verification_decision),
        )


def _response(
    *,
    source_text: str,
    rewritten_text: str,
    trace_id: str,
    decision: ReleaseDecision,
) -> RewriteResponse:
    return RewriteResponse(
        trace_id=trace_id,
        workflow_states=[
            "received",
            "ready_for_review",
        ],
        source_text=source_text,
        rewritten_text=rewritten_text,
        provider_name="test-provider",
        model_name="test-model",
        prompt_version="test-v1",
        provider_execution=(
            ProviderExecutionEvidence(
                latency_ms=0.0,
                primary_provider_name=("test-provider"),
                actual_provider_name=("test-provider"),
                fallback_used=False,
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                ),
            )
        ),
        rewrite_necessity=(
            RewriteNecessityEvidence(
                decision="full_rewrite",
                score=80,
                provider_required=True,
                signals=[],
                rationale=("Long-document adversarial test."),
            )
        ),
        analysis={
            "scores": {
                "generic_language": 0.0,
                "repetition": 0.0,
                "sentence_uniformity": 0.0,
                "transition_overuse": 0.0,
            },
            "flagged_segments": [],
        },
        editorial_quality=(
            EditorialQualityResult(
                decision=(EditorialQualityDecision.PASS),
                naturalness_score=1.0,
                source_flag_count=0,
                remaining_flag_count=0,
                removed_flag_count=0,
                remaining_flagged_segments=[],
                warnings=[],
            )
        ),
        protected_facts=[],
        changes=[],
        verification=VerificationResult(
            decision=decision,
            preserved_facts=[],
            missing_facts=[],
            unexpected_facts=[],
            warnings=[],
        ),
    )


def _install_services(
    workflow: AdversarialWorkflow,
    *,
    persistence_settings: (V2PersistenceSettings | None) = None,
) -> None:
    v2_routes.services = V2Services(
        workflow=cast(
            RewriteWorkflow,
            workflow,
        ),
        persistence_settings=(persistence_settings),
    )


def _workspace() -> tuple[str, str]:
    user_response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )

    assert user_response.status_code == 201

    user_id = user_response.json()["user"]["user_id"]

    workspace_response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "V2.5-I Workspace",
        },
    )

    assert workspace_response.status_code == 201

    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    return workspace_id, user_id


def _payload(
    *,
    user_id: str,
    text: str = SOURCE,
    enforcement_mode: str | None = None,
    protected_terms: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": user_id,
        "rewrite": {
            "text": text,
            "document_type": "general",
            "audience": ("engineering leadership"),
            "tone": "natural and clear",
            "intensity": ("deep_reconstruction"),
            "preserve_numbers": True,
            "preserve_dates": True,
        },
    }

    if enforcement_mode is not None:
        payload["claim_lock_enforcement_mode"] = enforcement_mode

    if protected_terms is not None:
        payload["protected_terms"] = protected_terms

    return payload


def _long_document_url(
    workspace_id: str,
) -> str:
    return f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"


def _audit_records(
    *,
    workspace_id: str,
    user_id: str,
) -> tuple[
    LongDocumentAuditRecord,
    ...,
]:
    return v2_routes.services.long_document_audit.list_workspace(
        workspace_id=workspace_id,
        user_id=user_id,
    )


def test_section_source_mismatch_fails_closed_without_audit() -> None:
    workflow = AdversarialWorkflow(
        (
            Scenario(
                source_text_override=("tampered section source"),
            ),
        )
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 409

    assert "source text" in response.json()["detail"]

    assert (
        _audit_records(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        == ()
    )


def test_later_section_v1_failure_creates_no_partial_audit() -> None:
    workflow = AdversarialWorkflow(
        (
            Scenario(),
            Scenario(
                verification_decision=(ReleaseDecision.FAIL),
            ),
        )
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 409
    assert len(workflow.requests) == 2

    assert (
        _audit_records(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        == ()
    )


def test_strict_cross_section_loss_fails_even_when_document_claim_lock_passes() -> None:
    workflow = AdversarialWorkflow(
        (
            Scenario(
                replace_from="Project Atlas",
                replace_to="The project",
            ),
            Scenario(),
        )
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
            text=CROSS_SECTION_SOURCE,
            enforcement_mode="strict",
            protected_terms=[
                {
                    "text": "Project Atlas",
                    "case_sensitive": True,
                }
            ],
        ),
    )

    assert response.status_code == 409

    assert "cross-section consistency" in response.json()["detail"]

    assert (
        _audit_records(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        == ()
    )


def test_audit_only_cross_section_loss_persists_violation_evidence() -> None:
    workflow = AdversarialWorkflow(
        (
            Scenario(
                replace_from="Project Atlas",
                replace_to="The project",
            ),
            Scenario(),
        )
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
            text=CROSS_SECTION_SOURCE,
            enforcement_mode="audit_only",
            protected_terms=[
                {
                    "text": "Project Atlas",
                    "case_sensitive": True,
                }
            ],
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["claim_lock"]["validation"]["decision"] == "pass"

    assert body["audit"]["cross_section_consistency"]["decision"] == "violation"

    records = _audit_records(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1

    assert records[0].cross_section_consistency.decision == "violation"


def test_crlf_document_round_trips_exactly_through_api_and_audit() -> None:
    workflow = AdversarialWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
            text=CRLF_SOURCE,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["reconstruction"]["reconstructed_text"] == CRLF_SOURCE

    assert body["audit"]["structure"]["source_text"] == CRLF_SOURCE

    records = _audit_records(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert len(records) == 1

    assert records[0].reconstruction.reconstructed_text == CRLF_SOURCE


def test_no_heading_document_remains_single_section() -> None:
    workflow = AdversarialWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    source = "A plain document without headings.\nIt remains one deterministic section.\n"

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
            text=source,
        ),
    )

    assert response.status_code == 200
    assert len(workflow.requests) == 1

    structure = response.json()["reconstruction"]["structure"]

    assert len(structure["sections"]) == 1

    assert response.json()["reconstruction"]["reconstructed_text"] == source


def test_nested_unknown_rewrite_field_is_422_without_execution() -> None:
    workflow = AdversarialWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    payload = _payload(
        user_id=user_id,
    )

    rewrite = cast(
        dict[str, object],
        payload["rewrite"],
    )
    rewrite["candidate_count"] = 2

    response = client.post(
        _long_document_url(workspace_id),
        json=payload,
    )

    assert response.status_code == 422
    assert workflow.requests == []


def test_invalid_claim_lock_mode_is_422_without_execution() -> None:
    workflow = AdversarialWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
            enforcement_mode=("disable-controls"),
        ),
    )

    assert response.status_code == 422
    assert workflow.requests == []


def test_long_document_audit_does_not_pollute_legacy_rewrite_history() -> None:
    workflow = AdversarialWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    long_document_response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert long_document_response.status_code == 200

    history_before = client.get(
        (f"/api/v2/workspaces/{workspace_id}/history"),
        params={
            "user_id": user_id,
        },
    )

    assert history_before.status_code == 200
    assert history_before.json()["records"] == []

    legacy_response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/rewrites"),
        json={
            "user_id": user_id,
            "rewrite": {
                "text": "Simple legacy source.",
                "document_type": "general",
                "audience": "general audience",
                "tone": "natural and clear",
                "intensity": "natural_rewrite",
                "preserve_numbers": True,
                "preserve_dates": True,
            },
        },
    )

    assert legacy_response.status_code == 200

    history_after = client.get(
        (f"/api/v2/workspaces/{workspace_id}/history"),
        params={
            "user_id": user_id,
        },
    )

    assert history_after.status_code == 200
    assert len(history_after.json()["records"]) == 1


def test_sqlite_long_document_audit_survives_service_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2-long-document.sqlite3"

    persistence = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )

    workflow = AdversarialWorkflow()

    _install_services(
        workflow,
        persistence_settings=persistence,
    )

    workspace_id, user_id = _workspace()

    response = client.post(
        _long_document_url(workspace_id),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200

    audit_id = response.json()["audit"]["audit_id"]

    recreated = V2Services(
        workflow=cast(
            RewriteWorkflow,
            AdversarialWorkflow(),
        ),
        persistence_settings=persistence,
    )

    stored = recreated.long_document_audit.get(
        workspace_id=workspace_id,
        user_id=user_id,
        audit_id=audit_id,
    )

    assert stored is not None
    assert stored.audit_id == audit_id
    assert stored.reconstruction.reconstructed_text == SOURCE
