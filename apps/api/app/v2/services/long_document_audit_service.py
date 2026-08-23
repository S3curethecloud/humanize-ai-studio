from __future__ import annotations

from uuid import uuid4

from app.v2.domain.long_document_audit import (
    CrossSectionConsistencyAuditCheck,
    CrossSectionConsistencyAuditSnapshot,
    LongDocumentAuditRecord,
)
from app.v2.domain.long_documents import (
    DocumentReconstruction,
)
from app.v2.repositories.long_document_audit import (
    LongDocumentAuditRepository,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluation,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class LongDocumentAuditIntegrityError(RuntimeError):
    pass


class LongDocumentAuditService:
    def __init__(
        self,
        *,
        repository: LongDocumentAuditRepository,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._repository = repository
        self._authorization_gate = authorization_gate

    def record(
        self,
        *,
        workspace_id: str,
        user_id: str,
        evaluation: LongDocumentControlEvaluation,
        reconstruction: DocumentReconstruction,
    ) -> LongDocumentAuditRecord:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.REWRITE_EXECUTE,
        )

        self._require_validated_artifact_linkage(
            evaluation=evaluation,
            reconstruction=reconstruction,
        )

        execution = evaluation.execution

        cross_section_snapshot = CrossSectionConsistencyAuditSnapshot(
            decision=(evaluation.cross_section_consistency.decision.value),
            checks=tuple(
                CrossSectionConsistencyAuditCheck(
                    section_id=check.section_id,
                    ordinal=check.ordinal,
                    item_id=check.item_id,
                    item_type=check.item_type,
                    expected_text=(check.expected_text),
                    status=check.status.value,
                )
                for check in (evaluation.cross_section_consistency.checks)
            ),
        )

        record = LongDocumentAuditRecord(
            audit_id=(f"long_document_audit_{uuid4().hex}"),
            workspace_id=workspace_id,
            user_id=user_id,
            structure=execution.structure,
            plan=execution.plan,
            reconstruction=reconstruction,
            claim_lock_validation=(evaluation.claim_lock_validation),
            cross_section_consistency=(cross_section_snapshot),
            v1_failed_section_ids=(evaluation.v1_failed_section_ids),
        )

        return self._repository.create(record)

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
        audit_id: str,
    ) -> LongDocumentAuditRecord | None:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.AUDIT_READ,
        )

        record = self._repository.get(audit_id)

        if record is not None and record.workspace_id != workspace_id:
            return None

        return record

    def list_workspace(
        self,
        *,
        workspace_id: str,
        user_id: str,
        limit: int = 50,
    ) -> tuple[
        LongDocumentAuditRecord,
        ...,
    ]:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.AUDIT_READ,
        )

        return self._repository.list_for_workspace(
            workspace_id=workspace_id,
            limit=limit,
        )

    def _require_validated_artifact_linkage(
        self,
        *,
        evaluation: LongDocumentControlEvaluation,
        reconstruction: DocumentReconstruction,
    ) -> None:
        if evaluation.v1_failed_section_ids:
            raise LongDocumentAuditIntegrityError(
                "long-document audit cannot persist a reconstruction with authoritative V1 failures"
            )

        execution = evaluation.execution

        if reconstruction.structure != execution.structure:
            raise LongDocumentAuditIntegrityError(
                "long-document audit reconstruction structure must match evaluated execution"
            )

        if reconstruction.section_results != execution.results:
            raise LongDocumentAuditIntegrityError(
                "long-document audit reconstruction results must match evaluated execution"
            )

        expected_text = "".join(result.rewritten_text for result in execution.results)

        if reconstruction.reconstructed_text != expected_text:
            raise LongDocumentAuditIntegrityError(
                "long-document audit reconstructed text must match evaluated ordered results"
            )
