from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ClaimLockEnforcementMode(StrEnum):
    STRICT = "strict"
    AUDIT_ONLY = "audit_only"


class ClaimLockOrigin(StrEnum):
    REQUEST = "request"
    WORKSPACE = "workspace"
    SYSTEM = "system"


class ProtectedValueKind(StrEnum):
    NUMBER = "number"
    DATE = "date"
    PERCENTAGE = "percentage"
    IDENTIFIER = "identifier"
    URL = "url"
    CODE = "code"
    OTHER = "other"


def _normalize_identifier(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")

    return normalized


def _normalize_text(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = " ".join(value.split())

    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")

    return normalized


class ClaimLockProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin: ClaimLockOrigin
    source_reference: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator(
        "source_reference",
        mode="before",
    )
    @classmethod
    def normalize_source_reference(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized = value.strip()

        return normalized or None


class ProtectedClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(
        min_length=1,
        max_length=200,
    )
    text: str = Field(
        min_length=1,
        max_length=10000,
    )
    provenance: ClaimLockProvenance

    @field_validator(
        "claim_id",
        mode="before",
    )
    @classmethod
    def normalize_claim_id(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_identifier(
            value,
            field_name="claim_id",
        )

    @field_validator(
        "text",
        mode="before",
    )
    @classmethod
    def normalize_claim_text(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_text(
            value,
            field_name="text",
        )

    def semantic_key(
        self,
    ) -> str:
        return self.text.casefold()


class ProtectedTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    term_id: str = Field(
        min_length=1,
        max_length=200,
    )
    text: str = Field(
        min_length=1,
        max_length=1000,
    )
    case_sensitive: bool = True
    provenance: ClaimLockProvenance

    @field_validator(
        "term_id",
        mode="before",
    )
    @classmethod
    def normalize_term_id(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_identifier(
            value,
            field_name="term_id",
        )

    @field_validator(
        "text",
        mode="before",
    )
    @classmethod
    def normalize_term_text(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_text(
            value,
            field_name="text",
        )

    def semantic_key(
        self,
    ) -> str:
        return self.text.casefold()


class ProtectedValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    value_id: str = Field(
        min_length=1,
        max_length=200,
    )
    value: str = Field(
        min_length=1,
        max_length=2000,
    )
    kind: ProtectedValueKind
    provenance: ClaimLockProvenance

    @field_validator(
        "value_id",
        mode="before",
    )
    @classmethod
    def normalize_value_id(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_identifier(
            value,
            field_name="value_id",
        )

    @field_validator(
        "value",
        mode="before",
    )
    @classmethod
    def normalize_protected_value(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_text(
            value,
            field_name="value",
        )

    def semantic_key(
        self,
    ) -> tuple[
        ProtectedValueKind,
        str,
    ]:
        return (
            self.kind,
            self.value.casefold(),
        )


class ClaimLock(BaseModel):
    model_config = ConfigDict(frozen=True)

    lock_id: str = Field(
        min_length=1,
        max_length=200,
    )
    enforcement_mode: ClaimLockEnforcementMode = ClaimLockEnforcementMode.STRICT

    claims: tuple[
        ProtectedClaim,
        ...,
    ] = ()
    terms: tuple[
        ProtectedTerm,
        ...,
    ] = ()
    values: tuple[
        ProtectedValue,
        ...,
    ] = ()

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "lock_id",
        mode="before",
    )
    @classmethod
    def normalize_lock_id(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return _normalize_identifier(
            value,
            field_name="lock_id",
        )

    @field_validator("created_at")
    @classmethod
    def require_timezone_aware_created_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        return value

    @model_validator(mode="after")
    def require_non_empty_lock(
        self,
    ) -> ClaimLock:
        if not (self.claims or self.terms or self.values):
            raise ValueError("claim lock must protect at least one item")

        return self

    @model_validator(mode="after")
    def reject_duplicate_identifiers(
        self,
    ) -> ClaimLock:
        identifiers = (
            tuple(claim.claim_id for claim in self.claims)
            + tuple(term.term_id for term in self.terms)
            + tuple(value.value_id for value in self.values)
        )

        normalized = tuple(identifier.casefold() for identifier in identifiers)

        if len(set(normalized)) != len(normalized):
            raise ValueError("claim lock item identifiers must be unique")

        return self

    @model_validator(mode="after")
    def reject_duplicate_protected_content(
        self,
    ) -> ClaimLock:
        claim_keys = tuple(claim.semantic_key() for claim in self.claims)

        if len(set(claim_keys)) != len(claim_keys):
            raise ValueError("claim lock contains duplicate protected claims")

        term_keys = tuple(term.semantic_key() for term in self.terms)

        if len(set(term_keys)) != len(term_keys):
            raise ValueError("claim lock contains duplicate protected terms")

        value_keys = tuple(value.semantic_key() for value in self.values)

        if len(set(value_keys)) != len(value_keys):
            raise ValueError("claim lock contains duplicate protected values")

        return self
