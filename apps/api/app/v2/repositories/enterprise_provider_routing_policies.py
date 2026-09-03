from __future__ import annotations

from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)


class EnterpriseProviderRoutingPolicyAlreadyExistsError(
    ValueError
):
    pass


class EnterpriseProviderRoutingPolicyRevisionConflictError(
    ValueError
):
    pass


class EnterpriseProviderRoutingPolicyIntegrityError(
    RuntimeError
):
    pass


class EnterpriseProviderRoutingPolicyNotFoundError(
    LookupError
):
    pass


class EnterpriseProviderRoutingPolicyArchivedError(
    ValueError
):
    pass


class EnterpriseWorkspaceProviderRoutingPolicyRepository(
    Protocol
):
    def create(
        self,
        policy: EnterpriseWorkspaceProviderRoutingPolicy,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy: ...

    def get_by_id(
        self,
        policy_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None: ...

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None: ...

    def update(
        self,
        policy: EnterpriseWorkspaceProviderRoutingPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy: ...


class InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository:
    def __init__(
        self,
    ) -> None:
        self._policies: dict[
            str,
            EnterpriseWorkspaceProviderRoutingPolicy,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        policy: EnterpriseWorkspaceProviderRoutingPolicy,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        _require_creatable_policy(policy)

        with self._lock:
            if policy.policy_id in self._policies:
                raise (
                    EnterpriseProviderRoutingPolicyAlreadyExistsError(
                        "enterprise provider routing policy "
                        "already exists: "
                        f"{policy.policy_id}"
                    )
                )

            if _current_workspace_policy_exists(
                stored_policies=self._policies,
                workspace_id=policy.workspace_id,
            ):
                raise (
                    EnterpriseProviderRoutingPolicyAlreadyExistsError(
                        "enterprise provider routing workspace "
                        "already has a non-archived policy"
                    )
                )

            candidate = dict(self._policies)
            candidate[policy.policy_id] = policy
            self._policies = candidate

        return policy

    def get_by_id(
        self,
        policy_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None:
        with self._lock:
            return self._policies.get(policy_id)

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy | None:
        with self._lock:
            matches = tuple(
                policy
                for policy in self._policies.values()
                if (
                    policy.workspace_id == workspace_id
                    and policy.status
                    is not EnterpriseProviderRoutingPolicyStatus.ARCHIVED
                )
            )

        return _require_unambiguous_workspace_policy(
            matches
        )

    def update(
        self,
        policy: EnterpriseWorkspaceProviderRoutingPolicy,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceProviderRoutingPolicy:
        with self._lock:
            stored = self._policies.get(
                policy.policy_id
            )

            if stored is None:
                raise EnterpriseProviderRoutingPolicyNotFoundError(
                    "enterprise provider routing policy "
                    "not found: "
                    f"{policy.policy_id}"
                )

            _validate_update_candidate(
                stored=stored,
                candidate=policy,
                expected_revision=expected_revision,
            )

            candidate_policies = dict(
                self._policies
            )
            candidate_policies[
                policy.policy_id
            ] = policy
            self._policies = candidate_policies

        return policy


def _require_creatable_policy(
    policy: EnterpriseWorkspaceProviderRoutingPolicy,
) -> None:
    if policy.revision != 1:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing policy "
            "must be created at revision 1"
        )

    if (
        policy.status
        is EnterpriseProviderRoutingPolicyStatus.ARCHIVED
    ):
        raise EnterpriseProviderRoutingPolicyArchivedError(
            "enterprise provider routing policy "
            "cannot be created archived"
        )


def _validate_update_candidate(
    *,
    stored: EnterpriseWorkspaceProviderRoutingPolicy,
    candidate: EnterpriseWorkspaceProviderRoutingPolicy,
    expected_revision: int,
) -> None:
    if (
        stored.status
        is EnterpriseProviderRoutingPolicyStatus.ARCHIVED
    ):
        raise EnterpriseProviderRoutingPolicyArchivedError(
            "enterprise provider routing policy "
            "is archived and cannot be updated"
        )

    if stored.revision != expected_revision:
        raise EnterpriseProviderRoutingPolicyRevisionConflictError(
            "enterprise provider routing policy revision "
            "conflict: "
            f"expected {expected_revision}, "
            f"stored {stored.revision}"
        )

    if candidate.revision != expected_revision + 1:
        raise EnterpriseProviderRoutingPolicyRevisionConflictError(
            "enterprise provider routing policy candidate "
            "revision must equal expected revision plus one"
        )

    if candidate.policy_id != stored.policy_id:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing policy_id "
            "is immutable"
        )

    if candidate.workspace_id != stored.workspace_id:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing workspace_id "
            "is immutable"
        )

    if candidate.policy_version != stored.policy_version:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing policy_version "
            "is immutable"
        )

    if (
        candidate.created_by_user_id
        != stored.created_by_user_id
    ):
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing "
            "created_by_user_id is immutable"
        )

    if candidate.created_at != stored.created_at:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing created_at "
            "is immutable"
        )

    if candidate.updated_at < stored.updated_at:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing updated_at "
            "must not move backwards"
        )

    _require_allowed_status_change(
        current=stored.status,
        requested=candidate.status,
    )


def _require_allowed_status_change(
    *,
    current: EnterpriseProviderRoutingPolicyStatus,
    requested: EnterpriseProviderRoutingPolicyStatus,
) -> None:
    if requested is current:
        return

    allowed: dict[
        EnterpriseProviderRoutingPolicyStatus,
        frozenset[
            EnterpriseProviderRoutingPolicyStatus
        ],
    ] = {
        EnterpriseProviderRoutingPolicyStatus.ACTIVE: (
            frozenset(
                {
                    EnterpriseProviderRoutingPolicyStatus.DISABLED,
                    EnterpriseProviderRoutingPolicyStatus.ARCHIVED,
                }
            )
        ),
        EnterpriseProviderRoutingPolicyStatus.DISABLED: (
            frozenset(
                {
                    EnterpriseProviderRoutingPolicyStatus.ACTIVE,
                    EnterpriseProviderRoutingPolicyStatus.ARCHIVED,
                }
            )
        ),
        EnterpriseProviderRoutingPolicyStatus.ARCHIVED: (
            frozenset()
        ),
    }

    if requested not in allowed[current]:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing policy lifecycle "
            "transition is not allowed: "
            f"{current.value} -> {requested.value}"
        )


def _current_workspace_policy_exists(
    *,
    stored_policies: dict[
        str,
        EnterpriseWorkspaceProviderRoutingPolicy,
    ],
    workspace_id: str,
) -> bool:
    return any(
        policy.workspace_id == workspace_id
        and policy.status
        is not EnterpriseProviderRoutingPolicyStatus.ARCHIVED
        for policy in stored_policies.values()
    )


def _require_unambiguous_workspace_policy(
    matches: tuple[
        EnterpriseWorkspaceProviderRoutingPolicy,
        ...,
    ],
) -> EnterpriseWorkspaceProviderRoutingPolicy | None:
    if not matches:
        return None

    if len(matches) != 1:
        raise EnterpriseProviderRoutingPolicyIntegrityError(
            "enterprise provider routing workspace "
            "has multiple non-archived policies"
        )

    return matches[0]
