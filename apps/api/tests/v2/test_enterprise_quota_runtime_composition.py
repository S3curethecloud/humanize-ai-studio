from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from app.v2.api import dependencies as v2_dependencies
from app.v2.api.dependencies import V2Services
from app.v2.services.enterprise_long_document_quota_admission_service import (
    EnterpriseLongDocumentQuotaAdmissionService,
)
from app.v2.services.enterprise_multi_candidate_quota_admission_service import (
    EnterpriseMultiCandidateQuotaAdmissionService,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    EnterpriseQuotaEnforcementService,
)
from app.v2.services.enterprise_quota_runtime import (
    EnterpriseQuotaRuntime,
)
from app.v2.services.enterprise_quota_runtime_context_service import (
    EnterpriseQuotaRuntimeContextService,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseSingleRewriteQuotaAdmissionService,
)
from app.workflows.rewrite_workflow import RewriteWorkflow


def _workflow() -> MagicMock:
    return MagicMock(spec=RewriteWorkflow)


def _runtime() -> tuple[
    EnterpriseQuotaRuntime,
    MagicMock,
    MagicMock,
]:
    runtime_context = MagicMock(
        spec=EnterpriseQuotaRuntimeContextService,
    )
    enforcement = MagicMock(
        spec=EnterpriseQuotaEnforcementService,
    )

    runtime = EnterpriseQuotaRuntime(
        limits=MagicMock(),
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    return runtime, runtime_context, enforcement


def test_quota_runtime_is_frozen_composition_contract() -> None:
    runtime, _runtime_context, _enforcement = _runtime()

    with pytest.raises(FrozenInstanceError):
        runtime.runtime_context = MagicMock()  # type: ignore[misc]


def test_no_runtime_preserves_single_rewrite_unmetered_composition() -> None:
    services = V2Services(
        workflow=_workflow(),
    )

    assert services.rewrite._quota_admission is None


def test_no_runtime_preserves_multi_candidate_unmetered_composition() -> None:
    services = V2Services(
        workflow=_workflow(),
    )

    assert (
        services.multi_candidate._multi_candidate_quota_admission
        is None
    )


def test_no_runtime_preserves_long_document_unmetered_composition() -> None:
    services = V2Services(
        workflow=_workflow(),
    )

    assert (
        services.long_document._long_document_quota_admission
        is None
    )


def test_global_v2services_remains_unmetered_by_default() -> None:
    assert v2_dependencies.services.rewrite._quota_admission is None
    assert (
        v2_dependencies.services.multi_candidate
        ._multi_candidate_quota_admission
        is None
    )
    assert (
        v2_dependencies.services.long_document
        ._long_document_quota_admission
        is None
    )


def test_runtime_injects_all_three_operation_adapters() -> None:
    runtime, _runtime_context, _enforcement = _runtime()

    services = V2Services(
        workflow=_workflow(),
        quota_runtime=runtime,
    )

    assert isinstance(
        services.rewrite._quota_admission,
        EnterpriseSingleRewriteQuotaAdmissionService,
    )
    assert isinstance(
        services.multi_candidate._multi_candidate_quota_admission,
        EnterpriseMultiCandidateQuotaAdmissionService,
    )
    assert isinstance(
        services.long_document._long_document_quota_admission,
        EnterpriseLongDocumentQuotaAdmissionService,
    )


def test_all_adapters_share_exact_runtime_context_authority() -> None:
    runtime, runtime_context, _enforcement = _runtime()

    services = V2Services(
        workflow=_workflow(),
        quota_runtime=runtime,
    )

    single = services.rewrite._quota_admission
    multi = services.multi_candidate._multi_candidate_quota_admission
    long_document = (
        services.long_document._long_document_quota_admission
    )

    assert single is not None
    assert multi is not None
    assert long_document is not None

    assert single._runtime_context is runtime_context
    assert multi._runtime_context is runtime_context
    assert long_document._runtime_context is runtime_context


def test_all_adapters_share_exact_enforcement_authority() -> None:
    runtime, _runtime_context, enforcement = _runtime()

    services = V2Services(
        workflow=_workflow(),
        quota_runtime=runtime,
    )

    single = services.rewrite._quota_admission
    multi = services.multi_candidate._multi_candidate_quota_admission
    long_document = (
        services.long_document._long_document_quota_admission
    )

    assert single is not None
    assert multi is not None
    assert long_document is not None

    assert single._enforcement is enforcement
    assert multi._enforcement is enforcement
    assert long_document._enforcement is enforcement


def test_runtime_composition_creates_distinct_operation_adapters() -> None:
    runtime, _runtime_context, _enforcement = _runtime()

    services = V2Services(
        workflow=_workflow(),
        quota_runtime=runtime,
    )

    single = services.rewrite._quota_admission
    multi = services.multi_candidate._multi_candidate_quota_admission
    long_document = (
        services.long_document._long_document_quota_admission
    )

    assert single is not None
    assert multi is not None
    assert long_document is not None

    assert single is not multi
    assert single is not long_document
    assert multi is not long_document
