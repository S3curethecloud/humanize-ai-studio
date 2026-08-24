from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION,
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)

POLICY_ID = "policy_test"
WORKSPACE_ID = "workspace_test"
CREATED_AT = datetime(
    2026,
    8,
    23,
    20,
    0,
    tzinfo=UTC,
)
UPDATED_AT = datetime(
    2026,
    8,
    23,
    20,
    5,
    tzinfo=UTC,
)


def _source_reference(
    *,
    policy_id: str = POLICY_ID,
    revision: int = 1,
) -> str:
    return (
        "workspace-claim-lock-policy:"
        f"{policy_id}:revision:{revision}"
    )


def _term(
    *,
    term_id: str = "term_product",
    text: str = "Humanize Enterprise",
    origin: ClaimLockOrigin = ClaimLockOrigin.WORKSPACE,
    source_reference: str | None = None,
    revision: int = 1,
) -> ProtectedTerm:
    return ProtectedTerm(
        term_id=term_id,
        text=text,
        case_sensitive=True,
        provenance=ClaimLockProvenance(
            origin=origin,
            source_reference=(
                source_reference
                if source_reference is not None
                else _source_reference(
                    revision=revision,
                )
            ),
        ),
    )


def _policy(
    **overrides: object,
) -> EnterpriseWorkspaceClaimLockPolicy:
    values: dict[str, object] = {
        "policy_id": POLICY_ID,
        "workspace_id": WORKSPACE_ID,
        "status": EnterpriseClaimLockPolicyStatus.ACTIVE,
        "enforcement_mode": (
            ClaimLockEnforcementMode.STRICT
        ),
        "protected_terms": (
            _term(),
        ),
        "created_by_user_id": "user_creator",
        "created_at": CREATED_AT,
        "updated_by_user_id": "user_editor",
        "updated_at": UPDATED_AT,
        "revision": 1,
    }
    values.update(overrides)

    return EnterpriseWorkspaceClaimLockPolicy(
        **values,
    )


def test_policy_uses_frozen_contract_version() -> None:
    policy = _policy()

    assert (
        policy.policy_version
        == ENTERPRISE_WORKSPACE_CLAIM_LOCK_POLICY_VERSION
    )
    assert (
        policy.policy_version
        == "enterprise-workspace-claim-lock-policy-v1"
    )


def test_policy_supports_exact_lifecycle_states() -> None:
    assert tuple(
        status.value
        for status in EnterpriseClaimLockPolicyStatus
    ) == (
        "active",
        "disabled",
        "archived",
    )


def test_policy_is_immutable() -> None:
    policy = _policy()

    with pytest.raises(ValidationError):
        policy.status = EnterpriseClaimLockPolicyStatus.DISABLED


def test_policy_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        _policy(unexpected_field="forbidden")


def test_policy_allows_empty_protected_terms() -> None:
    policy = _policy(
        protected_terms=(),
    )

    assert policy.protected_terms == ()


def test_policy_normalizes_bounded_identifiers() -> None:
    policy = _policy(
        policy_id="  policy_test  ",
        workspace_id="  workspace_test  ",
        created_by_user_id="  user_creator  ",
        updated_by_user_id="  user_editor  ",
    )

    assert policy.policy_id == POLICY_ID
    assert policy.workspace_id == WORKSPACE_ID
    assert policy.created_by_user_id == "user_creator"
    assert policy.updated_by_user_id == "user_editor"


@pytest.mark.parametrize(
    "field_name",
    (
        "policy_id",
        "workspace_id",
        "created_by_user_id",
        "updated_by_user_id",
    ),
)
def test_policy_rejects_blank_identifiers(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="must be non-empty",
    ):
        _policy(
            **{
                field_name: "   ",
            }
        )


def test_policy_rejects_revision_below_one() -> None:
    with pytest.raises(
        ValidationError,
        match="greater than or equal to 1",
    ):
        _policy(
            revision=0,
            protected_terms=(),
        )


def test_policy_requires_timezone_aware_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="created_at must be timezone-aware",
    ):
        _policy(
            created_at=datetime(
                2026,
                8,
                23,
                20,
                0,
            ),
        )


def test_policy_requires_timezone_aware_updated_at() -> None:
    with pytest.raises(
        ValidationError,
        match="updated_at must be timezone-aware",
    ):
        _policy(
            updated_at=datetime(
                2026,
                8,
                23,
                20,
                5,
            ),
        )


def test_policy_rejects_updated_at_before_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="must not be before created_at",
    ):
        _policy(
            updated_at=datetime(
                2026,
                8,
                23,
                19,
                59,
                tzinfo=UTC,
            ),
        )


def test_policy_requires_workspace_term_origin() -> None:
    with pytest.raises(
        ValidationError,
        match="must have workspace provenance",
    ):
        _policy(
            protected_terms=(
                _term(
                    origin=ClaimLockOrigin.REQUEST,
                ),
            ),
        )


def test_policy_requires_current_policy_source_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="current policy revision",
    ):
        _policy(
            protected_terms=(
                _term(
                    source_reference=(
                        "workspace-claim-lock-policy:"
                        "policy_other:revision:1"
                    ),
                ),
            ),
        )


def test_policy_requires_current_revision_source_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="current policy revision",
    ):
        _policy(
            revision=2,
            protected_terms=(
                _term(
                    revision=1,
                ),
            ),
        )


def test_policy_accepts_terms_for_current_revision() -> None:
    policy = _policy(
        revision=2,
        protected_terms=(
            _term(
                revision=2,
            ),
        ),
    )

    assert policy.revision == 2
    assert (
        policy.protected_terms[0]
        .provenance.source_reference
        == _source_reference(
            revision=2,
        )
    )


def test_policy_rejects_duplicate_term_ids_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate protected term identifiers",
    ):
        _policy(
            protected_terms=(
                _term(
                    term_id="term_one",
                    text="Humanize Enterprise",
                ),
                _term(
                    term_id="TERM_ONE",
                    text="Claim Lock",
                ),
            ),
        )


def test_policy_rejects_duplicate_term_semantic_content() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate protected terms",
    ):
        _policy(
            protected_terms=(
                _term(
                    term_id="term_one",
                    text="Humanize Enterprise",
                ),
                _term(
                    term_id="term_two",
                    text="humanize enterprise",
                ),
            ),
        )


def test_policy_rejects_wrong_contract_version() -> None:
    with pytest.raises(ValidationError):
        _policy(
            policy_version="enterprise-workspace-claim-lock-policy-v2",
        )
