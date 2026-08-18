from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
)
from app.v2.services.claim_extractor import (
    ClaimExtractionResult,
    ClaimExtractor,
    ClaimSelectionPolicy,
)
from app.v2.services.claim_lock_extractor import (
    ClaimLockExtractionResult,
    ClaimLockExtractor,
    ExplicitProtectedTerm,
)

_PREPARATION_VERSION: Literal["claim-lock-preparation-v1"] = "claim-lock-preparation-v1"


class ClaimLockPreparationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preparation_version: Literal["claim-lock-preparation-v1"] = _PREPARATION_VERSION

    claim_extraction: ClaimExtractionResult
    protected_item_extraction: ClaimLockExtractionResult
    claim_lock: ClaimLock | None

    @property
    def protected_item_count(
        self,
    ) -> int:
        if self.claim_lock is None:
            return 0

        return (
            len(self.claim_lock.claims) + len(self.claim_lock.terms) + len(self.claim_lock.values)
        )


class ClaimLockPreparationService:
    def __init__(
        self,
        *,
        claim_extractor: ClaimExtractor | None = None,
        protected_item_extractor: ClaimLockExtractor | None = None,
    ) -> None:
        self._claim_extractor = claim_extractor or ClaimExtractor()
        self._protected_item_extractor = protected_item_extractor or ClaimLockExtractor()

    def prepare(
        self,
        *,
        text: str,
        explicit_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_policy: ClaimSelectionPolicy | None = None,
        enforcement_mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
        origin: ClaimLockOrigin = (ClaimLockOrigin.REQUEST),
        source_reference: str | None = ("rewrite-request"),
    ) -> ClaimLockPreparationResult:
        claim_extraction = self._claim_extractor.extract(
            text=text,
            policy=claim_policy,
            origin=origin,
            source_reference=source_reference,
        )

        protected_item_extraction = self._protected_item_extractor.extract(
            text=text,
            explicit_terms=explicit_terms,
            origin=origin,
            source_reference=source_reference,
        )

        claims = claim_extraction.claims
        terms = protected_item_extraction.terms
        values = protected_item_extraction.values

        if not (claims or terms or values):
            return ClaimLockPreparationResult(
                claim_extraction=claim_extraction,
                protected_item_extraction=(protected_item_extraction),
                claim_lock=None,
            )

        lock_id = _stable_lock_id(
            enforcement_mode=enforcement_mode,
            claim_extraction=claim_extraction,
            protected_item_extraction=(protected_item_extraction),
        )

        claim_lock = ClaimLock(
            lock_id=lock_id,
            enforcement_mode=enforcement_mode,
            claims=claims,
            terms=terms,
            values=values,
        )

        return ClaimLockPreparationResult(
            claim_extraction=claim_extraction,
            protected_item_extraction=(protected_item_extraction),
            claim_lock=claim_lock,
        )


def _stable_lock_id(
    *,
    enforcement_mode: ClaimLockEnforcementMode,
    claim_extraction: ClaimExtractionResult,
    protected_item_extraction: ClaimLockExtractionResult,
) -> str:
    canonical_payload = {
        "preparation_version": (_PREPARATION_VERSION),
        "enforcement_mode": (enforcement_mode.value),
        "claim_extractor_version": (claim_extraction.extractor_version),
        "claim_policy": (claim_extraction.policy.model_dump(mode="json")),
        "protected_item_extractor_version": (protected_item_extraction.extractor_version),
        "claims": [claim.model_dump(mode="json") for claim in claim_extraction.claims],
        "terms": [term.model_dump(mode="json") for term in protected_item_extraction.terms],
        "values": [value.model_dump(mode="json") for value in protected_item_extraction.values],
    }

    canonical_bytes = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    digest = hashlib.sha256(canonical_bytes).hexdigest()[:20]

    return f"lock_{digest}"
