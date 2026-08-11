from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedClaim,
    ProtectedTerm,
    ProtectedValue,
    ProtectedValueKind,
)


def _provenance() -> ClaimLockProvenance:
    return ClaimLockProvenance(
        origin=ClaimLockOrigin.REQUEST,
        source_reference="rewrite-request",
    )


def test_claim_lock_defaults_to_strict_enforcement() -> None:
    lock = ClaimLock(
        lock_id="lock_1",
        claims=(
            ProtectedClaim(
                claim_id="claim_1",
                text="Revenue was 42 million in 2025.",
                provenance=_provenance(),
            ),
        ),
    )

    assert lock.enforcement_mode is ClaimLockEnforcementMode.STRICT


def test_claim_lock_models_are_frozen() -> None:
    claim = ProtectedClaim(
        claim_id="claim_1",
        text="Revenue was 42 million.",
        provenance=_provenance(),
    )

    with pytest.raises(ValidationError):
        claim.text = "Revenue was 50 million."  # type: ignore[misc]


def test_claim_lock_normalizes_identifiers_and_text() -> None:
    claim = ProtectedClaim(
        claim_id="  claim_1  ",
        text="  Revenue   was  42 million.  ",
        provenance=_provenance(),
    )

    assert claim.claim_id == "claim_1"
    assert claim.text == "Revenue was 42 million."


def test_claim_lock_rejects_empty_lock() -> None:
    with pytest.raises(
        ValidationError,
        match="must protect at least one item",
    ):
        ClaimLock(
            lock_id="lock_1",
        )


def test_claim_lock_rejects_blank_item_identifier() -> None:
    with pytest.raises(
        ValidationError,
        match="claim_id must be non-empty",
    ):
        ProtectedClaim(
            claim_id="   ",
            text="Revenue was 42 million.",
            provenance=_provenance(),
        )


def test_claim_lock_rejects_duplicate_ids_across_item_types() -> None:
    with pytest.raises(
        ValidationError,
        match="item identifiers must be unique",
    ):
        ClaimLock(
            lock_id="lock_1",
            claims=(
                ProtectedClaim(
                    claim_id="item_1",
                    text="Revenue was 42 million.",
                    provenance=_provenance(),
                ),
            ),
            terms=(
                ProtectedTerm(
                    term_id="ITEM_1",
                    text="SecureTheCloud",
                    provenance=_provenance(),
                ),
            ),
        )


def test_claim_lock_rejects_duplicate_claim_content() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate protected claims",
    ):
        ClaimLock(
            lock_id="lock_1",
            claims=(
                ProtectedClaim(
                    claim_id="claim_1",
                    text="Revenue was 42 million.",
                    provenance=_provenance(),
                ),
                ProtectedClaim(
                    claim_id="claim_2",
                    text="  REVENUE was 42 million. ",
                    provenance=_provenance(),
                ),
            ),
        )


def test_claim_lock_rejects_duplicate_term_content() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate protected terms",
    ):
        ClaimLock(
            lock_id="lock_1",
            terms=(
                ProtectedTerm(
                    term_id="term_1",
                    text="SecureTheCloud",
                    provenance=_provenance(),
                ),
                ProtectedTerm(
                    term_id="term_2",
                    text="securethecloud",
                    case_sensitive=False,
                    provenance=_provenance(),
                ),
            ),
        )


def test_claim_lock_rejects_duplicate_value_content_by_kind() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate protected values",
    ):
        ClaimLock(
            lock_id="lock_1",
            values=(
                ProtectedValue(
                    value_id="value_1",
                    value="42%",
                    kind=ProtectedValueKind.PERCENTAGE,
                    provenance=_provenance(),
                ),
                ProtectedValue(
                    value_id="value_2",
                    value="42%",
                    kind=ProtectedValueKind.PERCENTAGE,
                    provenance=_provenance(),
                ),
            ),
        )


def test_same_literal_can_be_protected_under_different_value_kinds() -> None:
    lock = ClaimLock(
        lock_id="lock_1",
        values=(
            ProtectedValue(
                value_id="value_1",
                value="2025",
                kind=ProtectedValueKind.NUMBER,
                provenance=_provenance(),
            ),
            ProtectedValue(
                value_id="value_2",
                value="2025",
                kind=ProtectedValueKind.DATE,
                provenance=_provenance(),
            ),
        ),
    )

    assert len(lock.values) == 2


def test_claim_lock_supports_all_three_protected_item_classes() -> None:
    lock = ClaimLock(
        lock_id="lock_1",
        claims=(
            ProtectedClaim(
                claim_id="claim_1",
                text="The deployment completed on June 3.",
                provenance=_provenance(),
            ),
        ),
        terms=(
            ProtectedTerm(
                term_id="term_1",
                text="Humanize AI Studio",
                provenance=ClaimLockProvenance(
                    origin=ClaimLockOrigin.WORKSPACE,
                    source_reference="brand-terms",
                ),
            ),
        ),
        values=(
            ProtectedValue(
                value_id="value_1",
                value="June 3",
                kind=ProtectedValueKind.DATE,
                provenance=_provenance(),
            ),
        ),
    )

    assert len(lock.claims) == 1
    assert len(lock.terms) == 1
    assert len(lock.values) == 1


def test_provenance_normalizes_blank_source_reference_to_none() -> None:
    provenance = ClaimLockProvenance(
        origin=ClaimLockOrigin.SYSTEM,
        source_reference="   ",
    )

    assert provenance.source_reference is None


def test_claim_lock_rejects_naive_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="created_at must be timezone-aware",
    ):
        ClaimLock(
            lock_id="lock_1",
            claims=(
                ProtectedClaim(
                    claim_id="claim_1",
                    text="Revenue was 42 million.",
                    provenance=_provenance(),
                ),
            ),
            created_at=datetime(
                2026,
                8,
                11,
                12,
                0,
                0,
            ),
        )


def test_claim_lock_accepts_timezone_aware_created_at() -> None:
    created_at = datetime(
        2026,
        8,
        11,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    lock = ClaimLock(
        lock_id="lock_1",
        claims=(
            ProtectedClaim(
                claim_id="claim_1",
                text="Revenue was 42 million.",
                provenance=_provenance(),
            ),
        ),
        created_at=created_at,
    )

    assert lock.created_at == created_at
