from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseClaimLockPolicyAlreadyExistsError,
    EnterpriseClaimLockPolicyArchivedError,
    EnterpriseClaimLockPolicyIntegrityError,
    EnterpriseClaimLockPolicyNotFoundError,
    EnterpriseClaimLockPolicyRevisionConflictError,
    EnterpriseWorkspaceClaimLockPolicyRepository,
)
from app.v2.repositories.enterprise_claim_lock_policy_admin_mutations import (
    EnterpriseClaimLockPolicyAdminMutationConfigurationError,
    EnterpriseClaimLockPolicyAdminMutationRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordInput,
    EnterpriseAdminAuditRecordingService,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
)


class ClaimLockAdministrationFailureReason(StrEnum):
    AUTHORIZATION_RESOLUTION_FAILED = (
        "authorization_resolution_failed"
    )
    AUTHORIZATION_DENIED = "authorization_denied"
    POLICY_NOT_FOUND = "policy_not_found"
    POLICY_ALREADY_EXISTS = "policy_already_exists"
    POLICY_ARCHIVED = "policy_archived"
    POLICY_NOT_ACTIVE = "policy_not_active"
    POLICY_ALREADY_ACTIVE = "policy_already_active"
    POLICY_ALREADY_DISABLED = "policy_already_disabled"
    POLICY_SCOPE_MISMATCH = "policy_scope_mismatch"
    REVISION_CONFLICT = "revision_conflict"
    INVALID_WORKSPACE_TERM = "invalid_workspace_term"
    PERSISTENCE_REJECTED = "persistence_rejected"
    TRANSACTION_REQUIRED = "transaction_required"


class EnterpriseClaimLockAdministrationError(
    RuntimeError
):
    def __init__(
        self,
        reason: ClaimLockAdministrationFailureReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason.value)


class EnterpriseClaimLockAdminService:
    def __init__(
        self,
        *,
        policies: EnterpriseWorkspaceClaimLockPolicyRepository,
        authorization_resolver: EnterpriseAuthorizationResolver,
        audit_recording: EnterpriseAdminAuditRecordingService,
        atomic_mutations: (
            EnterpriseClaimLockPolicyAdminMutationRepository
        ),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._policies = policies
        self._authorization_resolver = authorization_resolver
        self._audit_recording = audit_recording
        self._atomic_mutations = atomic_mutations
        self._clock = clock or _utc_now

    def get_policy(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        self._require_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            permission=EnterprisePermission.CLAIM_LOCK_READ,
        )

        try:
            policy = self._policies.get_for_workspace(
                workspace_id
            )
        except Exception as exc:
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason
                .PERSISTENCE_REJECTED
            ) from exc

        if policy is None:
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason.POLICY_NOT_FOUND
            )

        if policy.workspace_id != workspace_id:
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason
                .POLICY_SCOPE_MISMATCH
            )

        return policy


    def create_policy(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        policy_id: str,
        enforcement_mode: ClaimLockEnforcementMode,
        protected_terms: tuple[dict[str, Any], ...],
        status: EnterpriseClaimLockPolicyStatus = (
            EnterpriseClaimLockPolicyStatus.ACTIVE
        ),
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        action = (
            EnterpriseAdminAuditAction
            .CLAIM_LOCK_POLICY_CREATE
        )

        self._require_mutation_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            action=action,
            policy_id=policy_id,
        )

        if status is EnterpriseClaimLockPolicyStatus.ARCHIVED:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ARCHIVED
                ),
            )

        try:
            policy = self._build_policy(
                policy_id=policy_id,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                revision=1,
                status=status,
                enforcement_mode=enforcement_mode,
                protected_terms=protected_terms,
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .INVALID_WORKSPACE_TERM
                ),
                cause=exc,
            )

        try:
            event = self._build_success_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy.policy_id,
            )
        except Exception as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )

        try:
            return (
                self._atomic_mutations
                .create_policy_with_audit(
                    policy=policy,
                    audit_event=event,
                )
            )
        except EnterpriseClaimLockPolicyAlreadyExistsError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ALREADY_EXISTS
                ),
                cause=exc,
            )
        except EnterpriseClaimLockPolicyArchivedError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ARCHIVED
                ),
                cause=exc,
            )
        except (
            EnterpriseClaimLockPolicyAdminMutationConfigurationError
        ) as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .TRANSACTION_REQUIRED
                ),
                cause=exc,
            )
        except EnterpriseClaimLockPolicyIntegrityError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )
        except Exception as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )


    def update_policy(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        policy_id: str,
        expected_revision: int,
        enforcement_mode: ClaimLockEnforcementMode,
        protected_terms: tuple[dict[str, Any], ...],
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        action = (
            EnterpriseAdminAuditAction
            .CLAIM_LOCK_POLICY_UPDATE
        )

        self._require_mutation_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            action=action,
            policy_id=policy_id,
        )

        current = self._load_policy_for_mutation(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            policy_id=policy_id,
            action=action,
        )

        if (
            current.status
            is EnterpriseClaimLockPolicyStatus.ARCHIVED
        ):
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ARCHIVED
                ),
            )

        self._require_expected_revision(
            current=current,
            expected_revision=expected_revision,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
        )

        try:
            candidate = self._build_policy(
                policy_id=current.policy_id,
                workspace_id=current.workspace_id,
                actor_user_id=actor_user_id,
                revision=current.revision + 1,
                status=current.status,
                enforcement_mode=enforcement_mode,
                protected_terms=protected_terms,
                created_by_user_id=(
                    current.created_by_user_id
                ),
                created_at=current.created_at,
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .INVALID_WORKSPACE_TERM
                ),
                cause=exc,
            )

        return self._persist_update(
            current=current,
            candidate=candidate,
            expected_revision=expected_revision,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            action=action,
        )


    def enable_policy(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        policy_id: str,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        return self._change_status(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            policy_id=policy_id,
            expected_revision=expected_revision,
            status=EnterpriseClaimLockPolicyStatus.ACTIVE,
            action=EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ENABLE,
        )

    def disable_policy(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        policy_id: str,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        return self._change_status(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            policy_id=policy_id,
            expected_revision=expected_revision,
            status=EnterpriseClaimLockPolicyStatus.DISABLED,
            action=EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_DISABLE,
        )

    def archive_policy(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        policy_id: str,
        expected_revision: int,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        return self._change_status(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            policy_id=policy_id,
            expected_revision=expected_revision,
            status=EnterpriseClaimLockPolicyStatus.ARCHIVED,
            action=EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ARCHIVE,
        )

    def _change_status(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        policy_id: str,
        expected_revision: int,
        status: EnterpriseClaimLockPolicyStatus,
        action: EnterpriseAdminAuditAction,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        self._require_mutation_permission(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            action=action,
            policy_id=policy_id,
        )

        current = self._load_policy_for_mutation(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            policy_id=policy_id,
            action=action,
        )

        if (
            current.status
            is EnterpriseClaimLockPolicyStatus.ARCHIVED
        ):
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ARCHIVED
                ),
            )

        self._require_expected_revision(
            current=current,
            expected_revision=expected_revision,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
        )

        if (
            action
            is EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ENABLE
            and current.status
            is EnterpriseClaimLockPolicyStatus.ACTIVE
        ):
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ALREADY_ACTIVE
                ),
            )

        if (
            action
            is EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_DISABLE
            and current.status
            is EnterpriseClaimLockPolicyStatus.DISABLED
        ):
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ALREADY_DISABLED
                ),
            )

        new_revision = current.revision + 1

        protected_terms = tuple(
            {
                "term_id": term.term_id,
                "text": term.text,
                "case_sensitive": term.case_sensitive,
            }
            for term in current.protected_terms
        )

        try:
            candidate = self._build_policy(
                policy_id=current.policy_id,
                workspace_id=current.workspace_id,
                actor_user_id=actor_user_id,
                revision=new_revision,
                status=status,
                enforcement_mode=current.enforcement_mode,
                protected_terms=protected_terms,
                created_by_user_id=current.created_by_user_id,
                created_at=current.created_at,
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )

        return self._persist_update(
            current=current,
            candidate=candidate,
            expected_revision=expected_revision,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            action=action,
        )


    def _require_mutation_permission(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        action: EnterpriseAdminAuditAction,
        policy_id: str,
    ) -> None:
        try:
            self._require_permission(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                permission=EnterprisePermission.CLAIM_LOCK_MANAGE,
            )
        except EnterpriseClaimLockAdministrationError as exc:
            self._record_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.DENIED,
                policy_id=policy_id,
                failure_reason=exc.reason.value,
            )
            raise

    def _require_permission(
        self,
        *,
        actor_user_id: str,
        workspace_id: str,
        permission: EnterprisePermission,
    ) -> None:
        try:
            resolution = self._authorization_resolver.resolve(
                workspace_id=workspace_id,
                user_id=actor_user_id,
                permission=permission,
            )
        except Exception as exc:
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason
                .AUTHORIZATION_RESOLUTION_FAILED
            ) from exc

        if (
            resolution.status
            is not AuthorizationResolutionStatus.RESOLVED
        ):
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason
                .AUTHORIZATION_RESOLUTION_FAILED
            )

        if (
            resolution.authorization is None
            or resolution.authorization.decision
            is not AuthorizationDecision.ALLOW
        ):
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason
                .AUTHORIZATION_DENIED
            )


    def _load_policy_for_mutation(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        policy_id: str,
        action: EnterpriseAdminAuditAction,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        try:
            policy = self._policies.get_by_id(
                policy_id
            )
        except Exception as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )

        if policy is None:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_NOT_FOUND
                ),
            )

        if policy.workspace_id != workspace_id:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_SCOPE_MISMATCH
                ),
            )

        return policy

    def _require_expected_revision(
        self,
        *,
        current: EnterpriseWorkspaceClaimLockPolicy,
        expected_revision: int,
        workspace_id: str,
        actor_user_id: str,
        action: EnterpriseAdminAuditAction,
    ) -> None:
        if current.revision == expected_revision:
            return

        self._raise_mutation_failure(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            policy_id=current.policy_id,
            reason=(
                ClaimLockAdministrationFailureReason
                .REVISION_CONFLICT
            ),
        )

    def _persist_update(
        self,
        *,
        current: EnterpriseWorkspaceClaimLockPolicy,
        candidate: EnterpriseWorkspaceClaimLockPolicy,
        expected_revision: int,
        actor_user_id: str,
        workspace_id: str,
        action: EnterpriseAdminAuditAction,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        try:
            event = self._build_success_audit(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
            )
        except Exception as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )

        try:
            return (
                self._atomic_mutations
                .update_policy_with_audit(
                    policy=candidate,
                    expected_revision=expected_revision,
                    audit_event=event,
                )
            )
        except EnterpriseClaimLockPolicyRevisionConflictError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .REVISION_CONFLICT
                ),
                cause=exc,
            )
        except EnterpriseClaimLockPolicyArchivedError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_ARCHIVED
                ),
                cause=exc,
            )
        except EnterpriseClaimLockPolicyNotFoundError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .POLICY_NOT_FOUND
                ),
                cause=exc,
            )
        except (
            EnterpriseClaimLockPolicyAdminMutationConfigurationError
        ) as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .TRANSACTION_REQUIRED
                ),
                cause=exc,
            )
        except EnterpriseClaimLockPolicyIntegrityError as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )
        except Exception as exc:
            self._raise_mutation_failure(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                policy_id=current.policy_id,
                reason=(
                    ClaimLockAdministrationFailureReason
                    .PERSISTENCE_REJECTED
                ),
                cause=exc,
            )

    def _record_failed_mutation(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: EnterpriseAdminAuditAction,
        policy_id: str,
        reason: ClaimLockAdministrationFailureReason,
    ) -> None:
        self._record_audit(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            outcome=EnterpriseAdminAuditOutcome.FAILED,
            policy_id=policy_id,
            failure_reason=reason.value,
        )

    def _record_audit(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: EnterpriseAdminAuditAction,
        outcome: EnterpriseAdminAuditOutcome,
        policy_id: str,
        failure_reason: str | None = None,
    ) -> None:
        try:
            self._audit_recording.record(
                EnterpriseAdminAuditRecordInput(
                    workspace_id=workspace_id,
                    actor_user_id=actor_user_id,
                    action=action,
                    outcome=outcome,
                    target_type="claim_lock_policy",
                    target_id=policy_id,
                    failure_reason=failure_reason,
                )
            )
        except Exception as exc:
            raise EnterpriseClaimLockAdministrationError(
                ClaimLockAdministrationFailureReason
                .PERSISTENCE_REJECTED
            ) from exc

    def _raise_mutation_failure(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: EnterpriseAdminAuditAction,
        policy_id: str,
        reason: ClaimLockAdministrationFailureReason,
        cause: Exception | None = None,
    ) -> None:
        self._record_failed_mutation(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            policy_id=policy_id,
            reason=reason,
        )

        error = EnterpriseClaimLockAdministrationError(
            reason
        )

        if cause is None:
            raise error

        raise error from cause


    def _build_policy(
        self,
        *,
        policy_id: str,
        workspace_id: str,
        actor_user_id: str,
        revision: int,
        status: EnterpriseClaimLockPolicyStatus,
        enforcement_mode: ClaimLockEnforcementMode,
        protected_terms: tuple[dict[str, Any], ...],
        created_by_user_id: str | None = None,
        created_at: datetime | None = None,
    ) -> EnterpriseWorkspaceClaimLockPolicy:
        terms = tuple(
            self._build_workspace_term(
                item=item,
                policy_id=policy_id,
                revision=revision,
            )
            for item in protected_terms
        )

        now = self._clock()

        return EnterpriseWorkspaceClaimLockPolicy(
            policy_id=policy_id,
            workspace_id=workspace_id,
            status=status,
            enforcement_mode=enforcement_mode,
            protected_terms=terms,
            created_by_user_id=(
                created_by_user_id
                if created_by_user_id is not None
                else actor_user_id
            ),
            created_at=(
                created_at
                if created_at is not None
                else now
            ),
            updated_by_user_id=actor_user_id,
            updated_at=now,
            revision=revision,
        )

    @staticmethod
    def _build_workspace_term(
        *,
        item: dict[str, Any],
        policy_id: str,
        revision: int,
    ) -> ProtectedTerm:
        if not isinstance(item, dict):
            raise TypeError(
                "workspace protected term must be a mapping"
            )

        allowed_keys = {
            "term_id",
            "text",
            "case_sensitive",
        }

        if set(item) - allowed_keys:
            raise ValueError(
                "workspace protected term contains "
                "unsupported administrative fields"
            )

        term_id = item["term_id"]
        text = item["text"]
        case_sensitive = item.get(
            "case_sensitive",
            True,
        )

        if not isinstance(term_id, str):
            raise ValueError(
                "workspace protected term_id must be a string"
            )

        if not isinstance(text, str):
            raise ValueError(
                "workspace protected term text must be a string"
            )

        if not isinstance(case_sensitive, bool):
            raise ValueError(
                "workspace protected term case_sensitive "
                "must be boolean"
            )

        return ProtectedTerm(
            term_id=term_id,
            text=text,
            case_sensitive=case_sensitive,
            provenance=ClaimLockProvenance(
                origin=ClaimLockOrigin.WORKSPACE,
                source_reference=(
                    "workspace-claim-lock-policy:"
                    f"{policy_id}:revision:{revision}"
                ),
            ),
        )


    def _build_success_audit(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: EnterpriseAdminAuditAction,
        policy_id: str,
    ):
        return self._audit_recording.build_event(
            EnterpriseAdminAuditRecordInput(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
                target_type="claim_lock_policy",
                target_id=policy_id,
            )
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)
